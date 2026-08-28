"""Render stage: finalist clips + trajectories + captions → finished 9:16
MP4s, each verified (streams present, duration sane) before being reported."""

from __future__ import annotations

import json
from pathlib import Path

from ..jobs.queue import Stage, StageContext, StageError


def _caption_style_fingerprint(ctx: StageContext) -> dict:
    """Everything that changes how captions look on screen, resolved through
    the same layers the renderer uses (built-in → saved edits → job
    overrides) so editing a preset invalidates the render too."""
    from ..captions import ass as ass_mod

    preset = ass_mod.resolve_preset(
        ctx.settings.caption_preset, ctx.settings.captions.overrides
    )
    return preset.__dict__.copy()


def _load_clip_edits(job_dir: Path) -> dict:
    """Raw per-clip edits, or {} when the editor was never opened. Read as
    plain JSON rather than through edits.store so this stage stays free of a
    dependency on the editing package."""
    path = job_dir / "clip_edits.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        # UnicodeDecodeError is neither of the other two, and this read has
        # always been explicitly utf-8 — so a clip_edits.json an older build
        # wrote under the Windows ANSI codepage raised straight through
        # _clip_edits_fingerprint into artifacts_ok, crashing the render
        # fingerprint instead of answering it (§5.9).
        #
        # {} is the right degradation, not just the convenient one: run()
        # reads through this same function, so a job whose edits are
        # unreadable renders from job settings either way. A cached answer
        # therefore matches what re-running would actually produce, and a
        # clip that DID have edits still re-renders, because the stored
        # fingerprint no longer matches the empty one.
        return {}


def _previous_outputs(job_dir: Path) -> dict:
    """Last render's output entries keyed by clip index, so a clip this stage
    must not overwrite can be carried forward instead of vanishing."""
    path = job_dir / "render.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8")).get("data", {})
        return {str(o["clip"]): o for o in data.get("outputs", []) if Path(o["path"]).exists()}
    except (json.JSONDecodeError, OSError, KeyError, TypeError):
        return {}


def _has_structural_edits(edit: dict, clip: dict) -> bool:
    """Whether this clip was reshaped in a way this stage cannot reproduce.

    Bounds, dead-space removal and overlays all need the edit path's
    trim/concat/overlay graph. Style-only differences are applied here
    instead, so this deliberately does NOT count them.
    """
    if not edit:
        return False
    if edit.get("remove_dead_space") or edit.get("overlays"):
        return True
    try:
        return (
            abs(float(edit["start"]) - float(clip["start"])) > 0.05
            or abs(float(edit["end"]) - float(clip["end"])) > 0.05
        )
    except (KeyError, TypeError, ValueError):
        return False


def _clip_edits_fingerprint(job_dir: Path) -> dict:
    """Only the parts of each clip's edit that change its render, so opening
    the editor (which writes defaults) doesn't invalidate every render."""
    out: dict[str, dict] = {}
    for key, edit in _load_clip_edits(job_dir).items():
        if not isinstance(edit, dict):
            continue
        relevant = {
            k: edit.get(k)
            for k in (
                "start", "end", "caption_preset", "caption_overrides",
                "lufs_target", "true_peak_db", "letterbox_fill",
                "remove_dead_space", "disabled_cuts",
            )
            if edit.get(k) not in (None, {}, [])
        }
        if relevant:
            out[key] = relevant
    return out


def _audio_fingerprint(ctx: StageContext) -> dict:
    return {"lufs": ctx.settings.lufs_target, "true_peak": ctx.settings.true_peak_db}


def _encoder_fingerprint(ctx: StageContext) -> list[str]:
    """Which encoder produced these files. Switching to hardware encoding
    changes the bits, so it invalidates the render like any other visual
    setting."""
    from . import renderer

    return renderer.video_encoder_args(ctx.settings.performance.hardware_encode)


class RenderStage(Stage):
    name = "render"
    schema_version = 1

    def artifacts_ok(self, ctx: StageContext, data: dict) -> bool:
        if data.get("caption_preset") != ctx.settings.caption_preset:
            return False  # restyle requested → re-render
        if data.get("camera_settings") != ctx.settings.camera.__dict__:
            return False  # framing/camera restyle requested → re-render
        # Caption style edits (font/size/colors/words-per-caption) are burned
        # into the pixels, so they invalidate the render exactly like a preset
        # switch does. The saved-preset fingerprint covers edits made to the
        # named preset itself, not just this job's ad-hoc overrides.
        if data.get("caption_style") != _caption_style_fingerprint(ctx):
            return False
        if data.get("audio") != _audio_fingerprint(ctx):
            return False  # loudness targets are baked in by loudnorm
        if data.get("encoder") != _encoder_fingerprint(ctx):
            return False
        # A clip edited in the editor renders differently from the job's
        # settings, so editing one must re-run this stage — otherwise the
        # edit is only visible until the next restyle overwrites it.
        if (data.get("clip_edits") or {}) != _clip_edits_fingerprint(ctx.job_dir):
            return False
        return all(Path(c["path"]).exists() for c in data.get("outputs", []))

    def run(self, ctx: StageContext) -> dict:

        from ..captions import ass as ass_mod
        from . import ffmpeg_bin, renderer

        if not ffmpeg_bin.supports_captions():
            ctx.emit(-1, "No caption-capable ffmpeg found — fetching one…")
            if not ffmpeg_bin.ensure_capable(progress=lambda f, m: ctx.emit(f, m)):
                ctx.emit(-1, "Caption burning unavailable — rendering without captions.")

        prior = ctx.prior or {}
        ingest = prior.get("ingest")
        diarize = prior.get("diarize")
        events = prior.get("events")
        score = prior.get("score")
        camera = prior.get("camera")
        if not (ingest and diarize and events and score and camera):
            raise StageError("Render needs every prior stage output.", code="prior-stage-missing")

        media = ingest["media_path"]
        probe = ingest["probe"]
        src_w, src_h = int(probe["width"]), int(probe["height"])
        segments = diarize["segments"]
        timeline = events["timeline"]
        curves = json.loads(Path(events["curves_path"]).read_text(encoding="utf-8"))
        rms = curves["rms"]
        grid = float(curves["grid_sec"])

        captions_ok = ffmpeg_bin.supports_captions()
        emoji_ok = ass_mod.emoji_probe() if captions_ok else False
        ctx.emit(-1, f"Emoji support: {'yes' if emoji_ok else 'no (dropping emoji)'}")

        out_dir = ctx.job_dir / "clips"
        out_dir.mkdir(exist_ok=True)
        preset = ctx.settings.caption_preset
        outputs = []
        clips = score["clips"]

        # Per-clip edits are the user's most specific intent for a clip, and
        # this path used to ignore them completely — so a job-level restyle
        # silently re-rendered a hand-tuned clip at the job's settings,
        # discarding its framing, its caption tweaks, and (worst) its trimmed
        # bounds. Style overrides are applied below; structural edits (bounds,
        # dead-space cuts, overlays) need the edit path's trim/concat graph,
        # which this stage does not build, so those clips keep the render the
        # editor already produced and are reported rather than overwritten.
        clip_edits = _load_clip_edits(ctx.job_dir)
        previous = _previous_outputs(ctx.job_dir)
        kept_from_editor: list[int] = []

        for i, clip in enumerate(clips):
            traj_path = camera["trajectories"].get(str(i))
            if not traj_path or not Path(traj_path).exists():
                continue
            edit = clip_edits.get(str(i)) or {}

            # A clip the editor reshaped cannot be reproduced here; re-rendering
            # it from the job settings would throw that work away.
            if _has_structural_edits(edit, clip) and str(i) in previous:
                outputs.append(previous[str(i)])
                kept_from_editor.append(i)
                ctx.emit(
                    i / max(1, len(clips)),
                    f"Clip {i + 1} keeps its editor version (custom bounds/cuts)",
                )
                continue

            trajectory = json.loads(Path(traj_path).read_text(encoding="utf-8"))
            start, end = clip["start"], clip["end"]
            ctx.emit(i / max(1, len(clips)), f"Rendering clip {i + 1}/{len(clips)}…")

            # Words within the clip, clip-relative times.
            words = []
            for seg in segments:
                for w in seg.get("words", []):
                    if start <= w["start"] < end:
                        words.append(
                            ass_mod.Word(
                                text=w["word"],
                                start=round(w["start"] - start, 3),
                                end=round(min(w["end"], end) - start, 3),
                            )
                        )
            ass_mod.mark_emphasis(words, rms, grid, clip_start=start)
            clip_events = [
                {
                    "type": e["type"],
                    "start": round(max(0.0, e["start"] - start), 3),
                    "end": round(min(e["end"], end) - start, 3),
                }
                for e in timeline
                if e["end"] > start and e["start"] < end and e["type"] != "pause"
            ]
            # Style overrides this stage CAN honour, so a restyle doesn't
            # silently undo them. (The framing dial is baked into the
            # trajectory by the camera stage, so a per-clip gameplay_amount is
            # handled there, not here.)
            clip_preset = edit.get("caption_preset") or preset
            clip_caption_overrides = {
                **ctx.settings.captions.overrides,
                **(edit.get("caption_overrides") or {}),
            }
            clip_lufs = edit.get("lufs_target")
            clip_peak = edit.get("true_peak_db")
            clip_fill = edit.get("letterbox_fill") or ctx.settings.camera.letterbox_fill

            ass_path = out_dir / f"clip_{i:02d}.ass"
            ass_doc = ass_mod.build_ass(
                words, clip_events, preset_name=clip_preset, emoji_ok=emoji_ok,
                overrides=clip_caption_overrides,
            )
            ass_path.write_text(ass_doc, encoding="utf-8")

            out_path = out_dir / f"clip_{i:02d}.mp4"
            try:
                renderer.render_clip(
                    media, out_path, start, end, trajectory,
                    ass_path if captions_ok else None, ass_mod.FONTS_DIR,
                    lufs=clip_lufs if clip_lufs is not None else ctx.settings.lufs_target,
                    true_peak=clip_peak if clip_peak is not None else ctx.settings.true_peak_db,
                    src_w=src_w, src_h=src_h,
                    hardware_encode=ctx.settings.performance.hardware_encode,
                    letterbox_fill=clip_fill,
                )
            except RuntimeError as err:
                # renderer's message leads with raw ffmpeg stderr — headline
                # material for a developer, disclosure material for a user.
                raise StageError(
                    f"Clip {i} failed to encode.", code="render-failed", detail=str(err)
                ) from err
            check = renderer.verify_output(out_path, end - start)
            if not check["ok"]:
                raise StageError(
                    f"Clip {i} failed verification (duration {check['duration']:.1f}s, "
                    f"{check['width']}x{check['height']}).",
                    code="clip-verification-failed",
                )
            outputs.append(
                {
                    "clip": i,
                    "path": str(out_path),
                    "ass": str(ass_path),
                    "score": clip["score"],
                    "best_platform": clip["best_platform"],
                    "duration": round(check["duration"], 2),
                    "words": len(words),
                    "event_tags": len(clip_events),
                }
            )

        if not outputs:
            raise StageError("No clips were rendered.", code="no-clips-rendered")
        return {
            "outputs": outputs,
            "kept_from_editor": kept_from_editor,
            "emoji_ok": emoji_ok,
            "captions_burned": captions_ok,
            "caption_preset": preset,
            "camera_settings": ctx.settings.camera.__dict__.copy(),
            "caption_style": _caption_style_fingerprint(ctx),
            "audio": _audio_fingerprint(ctx),
            "encoder": _encoder_fingerprint(ctx),
            "clip_edits": _clip_edits_fingerprint(ctx.job_dir),
        }
