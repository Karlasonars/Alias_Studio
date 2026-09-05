"""Render stage: finalist clips + trajectories + captions → finished 9:16
MP4s, each verified (streams present, duration sane) before being reported.

One file per finalist, always. Ranking mode (E18, `settings.ranking.enabled`)
then adds up to two montages of the top moments under a numbered list —
render/ranking.py — appended to the same outputs list (D-18: as well as the
clips, never instead), and the checkpoint carries a `ranking` key that
artifacts_ok discriminates on, the same way it already discriminates on
`fills`. Three shapes exist on disk: no `ranking` key (a clip render), a
`ranking` without `montages` (the one-montage checkpoints E18-F02..F04
wrote, which serve nothing now), and `ranking.montages` (this build)."""

from __future__ import annotations

import json
from pathlib import Path

from ..camera.stage import sans_letterbox_fill
from ..captions import title as title_mod
from ..jobs.queue import Stage, StageContext, StageError
from . import watermark
from .inputs import clip_captions, clip_style, load_inputs


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


def _previous_render(job_dir: Path) -> dict:
    """Last render's checkpoint data, or {} when unreadable."""
    path = job_dir / "render.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8")).get("data", {})
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError, UnicodeDecodeError, AttributeError):
        return {}


def _previous_outputs(job_dir: Path) -> dict:
    """Last render's per-clip output entries keyed by clip index, so a clip
    this stage must not overwrite can be carried forward instead of
    vanishing. A ranking montage entry is never a clip's editor version —
    its `clip` is only the rank-1 index for the review panel — so it is
    skipped here: without that, a clip-mode run after a ranking run would
    adopt the montage as that clip's file."""
    try:
        return {
            str(o["clip"]): o
            for o in _previous_render(job_dir).get("outputs", [])
            if not o.get("montage") and Path(o["path"]).exists()
        }
    except (KeyError, TypeError, AttributeError):
        return {}


def _previous_montages(job_dir: Path) -> list[dict]:
    """The montage entries of the last render, in the order written: none
    for a clip render, one for the one-montage checkpoints E18-F02..F04
    wrote, up to two since D-18."""
    return [
        entry
        for entry in _previous_render(job_dir).get("outputs", []) or []
        if isinstance(entry, dict) and entry.get("montage")
    ]


def drop_reproducible_outputs(job_dir: Path) -> list[int]:
    """T-14's render invalidation: delete the rendered files this stage
    would re-encode anyway, keeping (a) render.json — _previous_outputs IS
    the adoption map — and (b) the files of structurally-edited clips,
    which run() adopts rather than reproduces. Deleting a kept file would
    silently downgrade adoption into a from-settings re-render, destroying
    the user's edit. The keep set is computed from CURRENT clip_edits, not
    the last run's kept_from_editor list, because a clip can gain
    structural edits after the render that recorded that list. Returns the
    dropped clip indices; empty when every clip is protected (then the
    resume is honestly a no-op).

    A ranking montage is always reproducible (nothing is ever adopted into
    it), so each is unlinked outright. Its `clip` — the rank-1 index — is
    reported only when no clip entry already did: since D-18 that clip has
    its own entry, and the one-montage shape carried nothing else."""
    previous = _previous_outputs(job_dir)
    edits = _load_clip_edits(job_dir)
    try:
        score = json.loads((job_dir / "score.json").read_text(encoding="utf-8"))
        clips = (score.get("data") or {}).get("clips") or []
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        clips = []
    dropped: list[int] = []
    for key, entry in previous.items():
        try:
            idx = int(key)
        except ValueError:
            continue
        clip = clips[idx] if 0 <= idx < len(clips) else {}
        if _has_structural_edits(edits.get(key) or {}, clip):
            continue
        Path(entry["path"]).unlink(missing_ok=True)
        dropped.append(idx)
    for montage in _previous_montages(job_dir):
        path = Path(str(montage.get("path", "")))
        if path.name and path.exists():
            path.unlink(missing_ok=True)
            idx = int(montage.get("clip", 0) or 0)
            if idx not in dropped:
                dropped.append(idx)
    return sorted(dropped)


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
        # E19-F01: the burned title, resolved exactly as the render resolves
        # it (whitespace-only is nothing), so the fingerprint cannot drift
        # from the thing it protects. An untouched clip stores "" and stays
        # out, as before the field existed.
        burned = title_mod.burned_title(edit)
        if burned:
            relevant["burned_title"] = burned
        if relevant:
            out[key] = relevant
    return out


def _effective_fill(edit: dict, settings) -> str:
    """The letterbox fill one clip actually renders with: its explicit
    per-clip value when set, else the job default (E6-F09). An untouched
    clip stores no fill key (None is dropped everywhere), so it follows the
    default; an explicit value — even one equal to the current default —
    stays put when the default changes.

    One function for run() AND the fingerprint (§5.8 applied inside a
    stage): resolving twice is how a fingerprint drifts from the thing it
    protects. The editor's render path (edits/render_clip.py) keeps its own
    copy of this expression against ClipEdit attributes; that copy predates
    this helper and is adjacent, not consequential."""
    return (edit or {}).get("letterbox_fill") or settings.camera.letterbox_fill


def _fill_keys(data: dict) -> list[str]:
    """Which clips a checkpoint's `fills` map covers: one per clip entry,
    montage entries skipped. artifacts_ok recomputes the map over exactly
    these keys. A montage entry carries its rank-1 clip's index (D-18 put
    the clips back beside the montages), so counting it would set a
    duplicate key against the map run() stored over the clips alone."""
    return [
        str(o.get("clip")) for o in data.get("outputs", []) if not o.get("montage")
    ]


def _fills_for(keys: list[str], edits: dict, settings) -> dict[str, str]:
    """The resolved fill per clip key — the one map both run() and
    artifacts_ok build, through the one helper, for either output unit."""
    return {key: _effective_fill(edits.get(key) or {}, settings) for key in keys}


def _audio_fingerprint(ctx: StageContext) -> dict:
    return {"lufs": ctx.settings.lufs_target, "true_peak": ctx.settings.true_peak_db}


def _encoder_fingerprint(ctx: StageContext) -> list[str]:
    """Which encoder produced these files. Switching to hardware encoding
    changes the bits, so it invalidates the render like any other visual
    setting."""
    from . import renderer

    return renderer.video_encoder_args(ctx.settings.performance.hardware_encode)


def _fingerprint(ctx: StageContext) -> dict:
    """The settings both output units bake into their files, as the
    checkpoint stores them. One builder so ranking and clip mode cannot
    disagree about what a re-render depends on."""
    return {
        "caption_preset": ctx.settings.caption_preset,
        "camera_settings": ctx.settings.camera.__dict__.copy(),
        "caption_style": _caption_style_fingerprint(ctx),
        "audio": _audio_fingerprint(ctx),
        "encoder": _encoder_fingerprint(ctx),
        "clip_edits": _clip_edits_fingerprint(ctx.job_dir),
        "watermark": watermark.fingerprint(ctx.settings),
    }


class RenderStage(Stage):
    name = "render"
    schema_version = 1

    def artifacts_ok(self, ctx: StageContext, data: dict) -> bool:
        # Output unit first (E18-F01): a ranking checkpoint serves a ranking
        # job and a clip checkpoint a clip job, never crosswise. Presence of
        # the key is the version, as with `fills`: every checkpoint written
        # before the feature lacks it and every settings snapshot from then
        # defaults the mode off, so old jobs take the path below untouched.
        want_ranking = bool(ctx.settings.ranking.enabled)
        stored_ranking = data.get("ranking") if isinstance(data.get("ranking"), dict) else None
        if want_ranking != (stored_ranking is not None):
            return False  # the output unit changed → re-render
        if stored_ranking is not None:
            if "montages" not in stored_ranking:
                # The one-montage checkpoint E18-F02..F04 wrote under D-17's
                # "one format, not both": a single montage entry and no clip
                # files. D-18 wants the clips too, so it cannot serve a
                # ranking job — the one re-render this reversal costs, paid
                # only by the ranking renders made in those days. Presence
                # of `montages` is the shape version, as `ranking` itself
                # is against clip checkpoints.
                return False
            if stored_ranking.get("count") != ctx.settings.ranking.count:
                return False  # a different top N is a different pair of videos
        if data.get("caption_preset") != ctx.settings.caption_preset:
            return False  # restyle requested → re-render
        if "fills" in data:
            # Fill-aware checkpoint (E6-F09). The job-level fill reaches only
            # the clips without an explicit per-clip value, so it is compared
            # as the RESOLVED per-clip result, never as a raw camera field: a
            # job whose clips all carry explicit fills must not re-render on
            # a default change, because the default never applied to them.
            # Known corner, accepted: a structurally-edited clip without an
            # explicit fill sits in the map too, so a default change can
            # re-run the stage even though adoption then keeps that clip
            # unchanged — over-invalidation only, never a lost edit.
            if sans_letterbox_fill(data.get("camera_settings") or {}) != sans_letterbox_fill(
                ctx.settings.camera.__dict__
            ):
                return False  # framing/camera restyle requested → re-render
            edits = _load_clip_edits(ctx.job_dir)
            if data["fills"] != _fills_for(_fill_keys(data), edits, ctx.settings):
                return False  # the fill some clip renders with changed
        else:
            # Legacy checkpoint, written before the fills map existed: the
            # old strict compare, byte for byte. Anything cleverer either
            # invalidates every render on disk the moment the feature
            # arrives (T-39's lesson) or quietly weakens invalidation for
            # old jobs — a fill change must still re-render them.
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
        # E19-F02: the mark is in every output's pixels. {} for none is
        # also what a checkpoint from before the setting existed reads as,
        # so a job that never had a mark keeps its render (§4 rule 3); a
        # logo replaced under the same path re-renders because the content
        # hash, not the path, is what differs (§4 rule 1).
        if (data.get("watermark") or {}) != watermark.fingerprint(ctx.settings):
            return False
        # A clip edited in the editor renders differently from the job's
        # settings, so editing one must re-run this stage — otherwise the
        # edit is only visible until the next restyle overwrites it.
        if (data.get("clip_edits") or {}) != _clip_edits_fingerprint(ctx.job_dir):
            return False
        return all(Path(c["path"]).exists() for c in data.get("outputs", []))

    def run(self, ctx: StageContext) -> dict:
        inputs = load_inputs(ctx, _load_clip_edits(ctx.job_dir))
        outputs, kept_from_editor, fills = _render_clips(ctx, inputs)
        if not outputs:
            raise StageError("No clips were rendered.", code="no-clips-rendered")
        data = {
            "outputs": outputs,
            "kept_from_editor": kept_from_editor,
            "emoji_ok": inputs.emoji_ok,
            "captions_burned": inputs.captions_ok,
            **_fingerprint(ctx),
            # Presence of this key is what routes artifacts_ok onto the
            # fill-aware path; old checkpoints without it keep the legacy
            # strict camera compare. Keys match the clip entries exactly:
            # every clip with a trajectory lands in both.
            "fills": fills,
        }
        if ctx.settings.ranking.enabled:
            from . import ranking

            montages, summary = ranking.render_montages(ctx, inputs, fills)
            # Clip entries first, montage entries after — the order the
            # review panel lists them in. No reader depends on it any more:
            # a montage entry carries its rank-1 clip's index, and every
            # reader that finds a clip by index (the editor's checkpoint
            # sync, _previous_outputs, _fill_keys) skips entries carrying
            # the `montage` marker instead of trusting position. Presence
            # of `ranking` is the shape version artifacts_ok discriminates
            # on (E18-F01, D-18).
            data["outputs"] = outputs + montages
            data["ranking"] = summary
        return data


def _render_clips(
    ctx: StageContext, inputs
) -> tuple[list[dict], list[int], dict[str, str]]:
    """The clip loop: one file per finalist with a trajectory, in every
    mode. Ranking mode adds its montages AFTER this and never instead of it
    (D-18): clips and ranking videos are two products of the same hour, and
    choosing between them meant running the job twice. Returns the output
    entries, the clips kept from the editor, and the resolved fill per clip.

    Per-clip edits are the user's most specific intent for a clip, and
    this path used to ignore them completely — so a job-level restyle
    silently re-rendered a hand-tuned clip at the job's settings,
    discarding its framing, its caption tweaks, and (worst) its trimmed
    bounds. Style overrides are applied below; structural edits (bounds,
    dead-space cuts, overlays) need the edit path's trim/concat graph,
    which this stage does not build, so those clips keep the render the
    editor already produced and are reported rather than overwritten.
    """
    from ..captions import ass as ass_mod
    from . import renderer

    outputs: list[dict] = []
    clips = inputs.clips
    clip_edits = inputs.clip_edits
    previous = _previous_outputs(ctx.job_dir)
    kept_from_editor: list[int] = []
    # Resolved fill per output clip, adopted ones included — the
    # fingerprint recomputes this same map with the same helper, and it
    # must cover every clip artifacts_ok will iterate.
    fills: dict[str, str] = {}

    for i, clip in enumerate(clips):
        traj_path = inputs.trajectories.get(str(i))
        if not traj_path or not Path(traj_path).exists():
            continue
        edit = clip_edits.get(str(i)) or {}
        fills.update(_fills_for([str(i)], clip_edits, ctx.settings))

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

        words, clip_events = clip_captions(inputs, start, end)
        style = clip_style(ctx, edit)
        preset = ass_mod.resolve_preset(style["preset"], style["overrides"])
        # E19-F01: the title the user marked, reproduced here as a style —
        # which is what lets a restyle keep it. E19-F02: the watermark,
        # placed for THIS clip's framing and under its captions. Both
        # through the functions the editor's render path calls (§5.8).
        title_styles, title_events = title_mod.overlay(
            preset, style["burned_title"], end - start
        )
        mark = watermark.compose(
            inputs.watermark, trajectory.get("content_w", 0), trajectory.get("content_h", 0),
            preset, end - start, say=lambda m: ctx.emit(-1, m),
        )

        ass_path = inputs.out_dir / f"clip_{i:02d}.ass"
        ass_doc = ass_mod.build_ass(
            words, clip_events, preset_name=style["preset"], emoji_ok=inputs.emoji_ok,
            overrides=style["overrides"],
            extra_styles=title_styles + mark.styles,
            extra_events=title_events + mark.events,
        )
        ass_path.write_text(ass_doc, encoding="utf-8")

        out_path = inputs.out_dir / f"clip_{i:02d}.mp4"
        try:
            renderer.render_clip(
                inputs.media, out_path, start, end, trajectory,
                ass_path if inputs.captions_ok else None, ass_mod.FONTS_DIR,
                lufs=style["lufs"], true_peak=style["true_peak"],
                src_w=inputs.src_w, src_h=inputs.src_h,
                hardware_encode=ctx.settings.performance.hardware_encode,
                letterbox_fill=fills[str(i)],
                overlay_vf=mark.vf,
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
    return outputs, kept_from_editor, fills
