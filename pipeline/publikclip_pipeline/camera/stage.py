"""Camera stage: run the director over the selected finalist clips only —
the single biggest GPU/CPU saving vs reference implementations that reframe
the whole hour (ARCHITECTURE-DRAFT stage 7)."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

from ..jobs.queue import Stage, StageContext, StageError
from ..models import registry, specs


def _clip_edits(job_dir: Path) -> dict:
    """Per-clip edits as raw JSON, or {} when the editor was never opened."""
    path = job_dir / "clip_edits.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _framing_fingerprint(job_dir: Path) -> dict:
    """The per-clip framing overrides only. Nothing else in a clip's edit
    changes its trajectory, so caption or audio tweaks must not force the
    (expensive) camera pass to run again."""
    out: dict[str, dict] = {}
    for key, edit in _clip_edits(job_dir).items():
        if not isinstance(edit, dict):
            continue
        picked = {
            k: edit.get(k)
            for k in ("camera_mode", "gameplay_amount")
            if edit.get(k) is not None
        }
        if picked:
            out[key] = picked
    return out


def sans_letterbox_fill(camera_dict: dict) -> dict:
    """A camera-settings dict without `letterbox_fill`.

    The fill is render-only: nothing in camera/ reads it (the director's
    content box comes from `gameplay_amount` alone), yet the strict
    `__dict__` compare in artifacts_ok re-ran the whole DIRECT pass —
    minutes of ASD — every time the fill changed. Excluded symmetrically,
    on the stored dict and the current one, so checkpoints written before
    this exclusion (which stored the key) stay valid. Render's fingerprint
    imports this same function for its own camera compare, so the two
    stages cannot disagree about which camera fields are render-only.
    """
    return {k: v for k, v in camera_dict.items() if k != "letterbox_fill"}


def _settings_for_clip(settings, edit: dict):
    """The job's settings with this clip's framing overrides on top.

    A whole Settings object (not a bare CameraSettings) so the director still
    sees `retention` — the punch-in envelope reads it, and handing it only the
    camera group would silently reset those knobs to their defaults.
    """
    from .. import config

    if not edit:
        return settings
    mode = edit.get("camera_mode")
    amount = edit.get("gameplay_amount")
    if not mode and amount is None:
        return settings
    camera = config.CameraSettings(**settings.camera.__dict__)
    if mode:
        camera.speaker_change = mode
    if amount is not None:
        camera.gameplay_amount = float(amount)
    return dataclasses.replace(settings, camera=camera)


class CameraStage(Stage):
    name = "camera"
    schema_version = 1

    def artifacts_ok(self, ctx: StageContext, data: dict) -> bool:
        if sans_letterbox_fill(data.get("camera_settings") or {}) != sans_letterbox_fill(
            ctx.settings.camera.__dict__
        ):
            return False  # camera style changed → re-direct
        # Punch-in shape/frequency is baked into the trajectory's zoom
        # envelope, so retention edits invalidate it exactly like a camera
        # mode switch does.
        if data.get("retention_settings") != ctx.settings.retention.__dict__:
            return False
        # Per-clip framing beats the job's dial for that clip, so changing it
        # must re-direct — and, just as importantly, a job-level restyle must
        # not quietly reproduce the old trajectory and drop the override.
        if (data.get("clip_framing") or {}) != _framing_fingerprint(ctx.job_dir):
            return False
        return all(Path(p).exists() for p in data.get("trajectories", {}).values())

    def run(self, ctx: StageContext) -> dict:
        import numpy as np

        from . import asd as asd_mod
        from . import director
        from .detect import FaceDetector

        prior = ctx.prior or {}
        ingest = prior.get("ingest")
        diarize = prior.get("diarize")
        events = prior.get("events")
        score = prior.get("score")
        if not (ingest and diarize and events and score):
            raise StageError(
                "Camera needs ingest + diarize + events + score outputs.",
                code="prior-stage-missing",
            )

        media = ingest["media_path"]
        probe = ingest["probe"]
        src_w, src_h = int(probe["width"]), int(probe["height"])

        ctx.emit(-1, "Loading vision models…")
        uf = registry.ensure(specs.ULTRAFACE, lambda f, m: ctx.emit(-1, m))
        fe = registry.ensure(specs.LR_ASD_FRONTEND, lambda f, m: ctx.emit(-1, m))
        be = registry.ensure(specs.LR_ASD_BACKEND, lambda f, m: ctx.emit(-1, m))
        detector = FaceDetector(str(uf))
        model = asd_mod.AsdModel(str(fe), str(be))

        curves = json.loads(Path(events["curves_path"]).read_text(encoding="utf-8"))
        dynamics = np.asarray(curves["dynamics"], dtype=float)
        grid = float(curves["grid_sec"])
        turns = diarize["turns"]
        timeline = events["timeline"]

        clips = score["clips"]
        edits = _clip_edits(ctx.job_dir)
        trajectories: dict[str, str] = {}
        stats = []
        for i, clip in enumerate(clips):
            start, end = clip["start"], clip["end"]
            settings = _settings_for_clip(ctx.settings, edits.get(str(i)) or {})
            note = "" if settings is ctx.settings else " (your framing for this clip)"
            ctx.emit(i / max(1, len(clips)), f"Directing clip {i + 1}/{len(clips)}…{note}")
            analysis = asd_mod.analyze_clip(media, start, end, detector, model, src_w, src_h)
            clip_turns = [t for t in turns if t["end"] > start and t["start"] < end]
            traj = director.build_trajectory(
                analysis, clip_turns, timeline, dynamics, grid,
                start, end, src_w, src_h, settings,
            )
            out_path = ctx.job_dir / f"trajectory_{i:02d}.json"
            payload = json.dumps(
                {
                    "clip_start": start,
                    "clip_end": end,
                    "fps": traj.fps,
                    "frames": traj.frames,
                    "cuts": traj.cuts,
                    "punches": traj.punches,
                    "content_w": traj.content_w,
                    "content_h": traj.content_h,
                    "meta": traj.meta,
                }
            )
            out_path.write_text(payload, encoding="utf-8")
            trajectories[str(i)] = str(out_path)
            stats.append(
                {
                    "clip": i,
                    "tracks": traj.meta["tracks"],
                    "switch_cuts": traj.meta["switch_cuts"],
                    "shot_cuts": traj.meta["shot_cuts"],
                    "punches": len(traj.punches),
                }
            )

        return {
            "trajectories": trajectories,
            "stats": stats,
            "camera_settings": ctx.settings.camera.__dict__.copy(),
            "retention_settings": ctx.settings.retention.__dict__.copy(),
            "clip_framing": _framing_fingerprint(ctx.job_dir),
        }
