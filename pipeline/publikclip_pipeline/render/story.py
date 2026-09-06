"""Story render stage (E20-F03, F04, F05): background + narration + captions
→ one finished 9:16 MP4, verified before it is reported.

The story chain's last stage, named `render` like the clips chain's
(D-20): the library rail, `job_results`, the review panel and the
calibration scan all key on `render.json`, and they behave well with one
story entry in `outputs`. The cost D-20 accepted is two guards, both here
or next to their callers: `drop_reproducible_outputs` treats a story
entry as always reproducible (nothing is ever adopted into it), and the
cancel cleanup probes it like any other entry because it carries `path`
and `duration`.

What one render does (F03): the background is looped when shorter than
the narration and trimmed when longer (`-stream_loop -1` plus `-t`), its
own audio is never mapped, and a non-9:16 picture is covered and
centre-cropped through `renderer.cover_vf` — the same expression the
letterbox blur fill uses for its backdrop, so the two never disagree
about geometry. The narration is the only audio; loudnorm and the
encoder come from renderer.py exactly as for a clip (T-42: one encoder
path, one verification path).

Captions (F04): the words come from `asr` transcribing the narration —
never from the synthesiser — so a caption lands where the ear hears the
word. Same `captions/ass.py`, same presets; one-word-at-a-time is the
preset's `max_words` at 1 (the built-in `story` preset), not a mechanism.
Words that fall inside the title's audio are not captioned: the card
(captions/story_card.py, F05) shows the title instead.

The card (F05, channel-card amendment): the title under a header of the
user's channel name and an avatar, over a meta row carrying the narration's
duration. The avatar is the watermark PNG (E19-F02), resolved through the
same `watermark.resolve` the mark itself uses — one file, one hash in the
fingerprint — and overlaid by `avatar_vf` AFTER the caption burn, because
the card's panel is drawn by the ASS and would cover a picture placed under
it. It is enabled only while the card is up and switched off as the card's
fade-out begins, so it never floats alone after the panel has gone; with
no PNG the ASS draws the channel's initial on the accent colour instead.

Fingerprint (§4 rule 1): everything this stage bakes into the pixels and
the sound — the caption preset and its resolved style, the loudness
targets, the encoder, the watermark (which is also the avatar), the
channel name and the card's drawing version. The narration and the words
reach here through the cascade (rule 2), so they need no key; the
duration on the card is the narration's, so a re-narration re-renders it
through that cascade too. No story checkpoint predates this build, so
the compares are strict; `story: True` is the shape marker that keeps a
clip checkpoint from ever serving a story job or the reverse.
"""

from __future__ import annotations

from pathlib import Path

from ..captions import ass as ass_mod
from ..captions import story_card
from ..jobs.queue import Stage, StageContext, StageError
from . import renderer, watermark

OUTPUT_NAME = "story.mp4"
STORY_PRESET = "story"
# Silence after the narrator's last word, so the file does not end on the
# consonant: the background keeps playing under it.
TAIL_SEC = 0.6
# A word whose start is inside the title's audio by less than this is the
# title being transcribed slightly late; it belongs to the card, not the
# captions.
TITLE_SLACK_SEC = 0.05


def _caption_style_fingerprint(ctx: StageContext) -> dict:
    preset = ass_mod.resolve_preset(ctx.settings.caption_preset, ctx.settings.captions.overrides)
    return preset.__dict__.copy()


def channel_name(settings) -> str:
    """The name on the card, whitespace-normalised: what the fingerprint
    compares and what is drawn, so the two cannot differ by a space."""
    return " ".join(str(settings.story.channel_name or "").split())


def _fingerprint(ctx: StageContext) -> dict:
    return {
        "caption_preset": ctx.settings.caption_preset,
        "caption_style": _caption_style_fingerprint(ctx),
        "audio": {"lufs": ctx.settings.lufs_target, "true_peak": ctx.settings.true_peak_db},
        "encoder": renderer.video_encoder_args(ctx.settings.performance.hardware_encode),
        # The watermark entry is also the avatar's: same path, same sha256.
        # No second hash on purpose — two entries for one file could drift.
        "watermark": watermark.fingerprint(ctx.settings),
        "channel_name": channel_name(ctx.settings),
        "card_version": story_card.CARD_VERSION,
    }


def avatar_vf(path: str, end_sec: float) -> str:
    """The graph fragment that puts the PNG in the card's avatar circle:
    loaded by `movie`, scaled to cover the circle's square and centre-
    cropped to it, then masked to a disc through `geq` on the alpha plane
    (planar RGBA in, `hypot` from the centre against the radius), and
    overlaid on the card's pixels only while the card is up. Same label
    discipline as the watermark's fragment (`av_*`), and it composes after
    the subtitle burn — see the module docstring for why after.

    The overlay ends where the card's fade-out begins rather than at
    `end_sec`: `overlay` has no fade, and a picture lingering at full
    opacity over a panel that is dissolving reads as a glitch, while a
    picture that goes as the dissolve starts reads as part of it.
    """
    x, y, d = story_card.avatar_box()
    r = d / 2
    chain = (
        f"movie=filename={renderer._q(path)}"  # noqa: SLF001 — the one portable quoting
        f",scale={d}:{d}:force_original_aspect_ratio=increase:flags=lanczos,crop={d}:{d}"
        f",format=gbrap,geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)'"
        f":a='alpha(X,Y)*lte(hypot(X+0.5-{r:g},Y+0.5-{r:g}),{r:g})',format=rgba"
    )
    until = max(0.0, float(end_sec) - story_card.FADE_OUT_MS / 1000.0)
    return (
        f"null[av_base];{chain}[av_src];"
        f"[av_base][av_src]overlay=x={x}:y={y}:enable='between(t,0,{until:.3f})'"
    )


def caption_words(segments: list, title_end_sec: float) -> list[ass_mod.Word]:
    """The narration's words after the title, in the output's own time —
    the narration starts at 0 in the file, so no shift is needed."""
    words: list[ass_mod.Word] = []
    for seg in segments:
        for w in seg.get("words", []):
            start = float(w["start"])
            if start < title_end_sec - TITLE_SLACK_SEC:
                continue
            words.append(
                ass_mod.Word(text=w["word"], start=round(start, 3), end=round(float(w["end"]), 3))
            )
    return words


class StoryRenderStage(Stage):
    name = "render"
    schema_version = 1

    def artifacts_ok(self, ctx: StageContext, data: dict) -> bool:
        if not data.get("story"):
            return False  # a clip checkpoint never serves a story job
        current = _fingerprint(ctx)
        for key, value in current.items():
            if data.get(key) != value:
                return False
        outputs = data.get("outputs") or []
        return bool(outputs) and all(Path(o["path"]).exists() for o in outputs)

    def run(self, ctx: StageContext) -> dict:
        from . import ffmpeg_bin

        prior = ctx.prior or {}
        ingest, narrate, asr = prior.get("ingest"), prior.get("narrate"), prior.get("asr")
        if not (ingest and narrate and asr):
            raise StageError("The story render needs ingest, narrate and asr.", code="prior-stage-missing")
        background = Path(str(ingest.get("media_path") or ""))
        narration = Path(str(narrate.get("audio_path") or ""))
        if not background.exists() or not narration.exists():
            raise StageError(
                "The background or the narration is missing from this job.", code="prior-stage-missing"
            )

        if not ffmpeg_bin.supports_captions():
            ctx.emit(-1, "No caption-capable ffmpeg found — fetching one…")
            if not ffmpeg_bin.ensure_capable(progress=lambda f, m: ctx.emit(f, m)):
                ctx.emit(-1, "Caption burning unavailable — rendering without captions.")
        captions_ok = ffmpeg_bin.supports_captions()
        emoji_ok = ass_mod.emoji_probe() if captions_ok else False

        title = str(narrate.get("title") or "")
        title_end = float(narrate.get("title_end_sec") or 0.0)
        duration = float(narrate["duration_sec"]) + TAIL_SEC
        words = caption_words(asr.get("segments") or [], title_end)

        preset_name = ctx.settings.caption_preset
        overrides = ctx.settings.captions.overrides
        preset = ass_mod.resolve_preset(preset_name, overrides)
        # One resolution of the watermark for both of its uses: the mark
        # under the captions and the card's avatar. A PNG that is missing
        # or not a PNG is None here, said once, and the card falls back to
        # the initial — the same degradation the mark takes (§5.9).
        resolved = watermark.resolve(ctx.settings, say=lambda m: ctx.emit(-1, m))
        avatar = resolved.path if resolved is not None and resolved.kind == "image" else ""
        card = story_card.Card(
            title=title, end_sec=title_end, channel=channel_name(ctx.settings),
            duration_sec=float(narrate["duration_sec"]), avatar=avatar,
        )
        card_styles, card_events = story_card.overlay(preset, card)
        # The picture covers the canvas, so the mark takes its on-picture
        # placement under the captions, through the one function every
        # render path calls (§5.8).
        mark = watermark.compose(
            resolved, renderer.OUT_W, renderer.OUT_H, preset, duration,
            say=lambda m: ctx.emit(-1, m),
        )

        out_dir = ctx.job_dir / "clips"
        out_dir.mkdir(exist_ok=True)
        ass_path = out_dir / "story.ass"
        doc = ass_mod.build_ass(
            words, [], preset_name=preset_name, emoji_ok=emoji_ok, overrides=overrides,
            extra_styles=card_styles + mark.styles, extra_events=card_events + mark.events,
        )
        ass_path.write_text(doc, encoding="utf-8")

        # The picture avatar exists only where the card does: no card (no
        # title, no time) or no caption burn means no ASS panel, and a
        # picture without its panel would float on the background alone.
        after_vf = avatar_vf(avatar, title_end) if avatar and card_events and captions_ok else ""

        out_path = out_dir / OUTPUT_NAME
        ctx.emit(0.1, f"Rendering the story ({duration:.0f} s)…")
        try:
            renderer.render_story(
                str(background), str(narration), out_path, duration,
                ass_path if captions_ok else None, ass_mod.FONTS_DIR,
                lufs=ctx.settings.lufs_target, true_peak=ctx.settings.true_peak_db,
                hardware_encode=ctx.settings.performance.hardware_encode,
                overlay_vf=mark.vf, after_vf=after_vf,
            )
        except RuntimeError as err:
            raise StageError("The story failed to encode.", code="render-failed", detail=str(err)) from err
        check = renderer.verify_output(out_path, duration)
        if not check["ok"]:
            raise StageError(
                f"The story failed verification (duration {check['duration']:.1f}s, "
                f"{check['width']}x{check['height']}).",
                code="clip-verification-failed",
            )
        return {
            "story": True,
            "outputs": [
                {
                    "clip": 0,
                    "story": True,
                    "path": str(out_path),
                    "ass": str(ass_path),
                    "title": title,
                    "duration": round(check["duration"], 2),
                    "words": len(words),
                    "event_tags": 0,
                }
            ],
            "title": title,
            "title_end_sec": title_end,
            # What the card showed, for the reader of the job dir: the
            # avatar's file ("" = the initial) and the one number on it.
            "card": {"avatar": avatar, "duration_label": story_card.duration_label(card.duration_sec)},
            "emoji_ok": emoji_ok,
            "captions_burned": captions_ok,
            **_fingerprint(ctx),
        }
