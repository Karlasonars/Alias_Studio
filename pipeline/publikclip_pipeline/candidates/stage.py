"""Candidates stage: build every free channel, weigh them into the interest
curve, extract ~35 sentence-snapped candidate windows. No LLM spend here —
this count is the cost gate for T1/T2."""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path

from .. import config
from ..jobs.queue import Stage, StageContext, StageError


class _FactoryCtx:
    """Minimal stand-in for StageContext so a stage can compute what its
    fingerprint would look like under untouched defaults."""

    def __init__(self, settings: "config.Settings"):
        self.settings = settings

_TIME_RE = re.compile(r"time=(\d+):(\d\d):(\d\d(?:\.\d+)?)")
_PTS_RE = re.compile(r"pts_time:([0-9.]+)")


def detect_scenes_ffmpeg(
    media_path: str,
    threshold: float = 0.35,
    height: int = 180,
    progress=None,
) -> list[float] | None:
    """Scene cuts via ffmpeg's own `scene` filter. Returns None on any
    failure so the caller can fall back to PySceneDetect.

    Why this exists: PySceneDetect decodes and compares every frame in
    Python. On an 81-minute source that measured 48+ minutes — comparable to
    the entire transcription — to feed an interest channel weighted 0.05.
    ffmpeg does the same comparison in C, on frames downscaled to `height`
    before comparison, and can hand decoding to the GPU. The cut list is not
    identical to PySceneDetect's (different algorithm, different threshold
    scale) but serves the same two consumers: a low-weight interest channel
    and frame sampling for the visual pass.
    """
    from ..render import ffmpeg_bin

    out_dir = Path(tempfile.mkdtemp(prefix="publikclip-scenes-"))
    meta_path = out_dir / "scenes.txt"
    # ffmpeg's metadata filter wants a forward-slashed, escaped path.
    meta_arg = str(meta_path).replace("\\", "/").replace(":", "\\:")
    vf = (
        f"scale=-2:{height},select='gt(scene\\,{threshold})',"
        f"metadata=print:file='{meta_arg}'"
    )
    args = [
        ffmpeg_bin.ffmpeg(), "-hide_banner", "-y",
        "-i", media_path,
        "-vf", vf,
        "-an", "-sn", "-f", "null", "-",
    ]
    try:
        proc = subprocess.Popen(
            args, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            text=True, errors="replace",
        )
        assert proc.stderr is not None
        duration = _probe_duration(media_path)
        for line in proc.stderr:
            if progress and duration:
                m = _TIME_RE.search(line)
                if m:
                    secs = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
                    progress(min(1.0, secs / duration))
        code = proc.wait(timeout=3 * 3600)
        if code != 0:
            return None
        # PySceneDetect returns scene START times, which includes 0.0 for the
        # opening shot; ffmpeg reports only the change points. Prepend 0.0 so
        # both paths hand downstream the same shape and the setting is a true
        # swap rather than a subtly different signal.
        if not meta_path.exists():
            return [0.0]  # no detected cut is a legitimate result: one shot
        text = meta_path.read_text(encoding="utf-8", errors="replace")
        cuts = [round(float(t), 3) for t in _PTS_RE.findall(text)]
        return [0.0] + [t for t in cuts if t > 0.05]
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    finally:
        try:
            meta_path.unlink(missing_ok=True)
            out_dir.rmdir()
        except OSError:
            pass


def _probe_duration(media_path: str) -> float:
    from ..render import ffmpeg_bin

    try:
        out = subprocess.run(
            [
                ffmpeg_bin.ffprobe(), "-v", "error", "-show_entries",
                "format=duration", "-of", "default=nw=1:nk=1", media_path,
            ],
            capture_output=True, text=True, timeout=120,
        )
        return float(out.stdout.strip())
    except (OSError, subprocess.SubprocessError, ValueError):
        return 0.0


def detect_scenes(media_path: str, progress=None) -> list[float]:
    """Scene-change timestamps via PySceneDetect ContentDetector (BSD-3) on
    a downscaled decode. On a static podcast this returns camera cuts; on
    gaming/vlog footage it captures visual pacing.

    This is a full frame-by-frame decode — tens of thousands of frames on a
    longer video — so it reports fractional progress via `callback` instead
    of sitting silent for however long that takes (throttled to ~1% steps;
    PySceneDetect calls back per decoded frame and unthrottled JSONL/IPC
    traffic at that rate would swamp the UI for no benefit)."""
    from scenedetect import ContentDetector, open_video
    from scenedetect.scene_manager import SceneManager

    video = open_video(media_path)
    total_sec = video.duration.get_seconds() if video.duration else 0
    last_reported = -1.0

    def _on_frame(_frame, timecode) -> None:
        nonlocal last_reported
        if not progress or not total_sec:
            return
        fraction = min(1.0, timecode.get_seconds() / total_sec)
        if fraction - last_reported >= 0.01:
            last_reported = fraction
            progress(fraction)

    manager = SceneManager()
    manager.add_detector(ContentDetector(threshold=27.0))
    manager.auto_downscale = True
    manager.detect_scenes(video, show_progress=False, callback=_on_frame)
    return [start.get_seconds() for start, _ in manager.get_scene_list()]


class CandidatesStage(Stage):
    name = "candidates"
    schema_version = 1

    @staticmethod
    def _settings_used(ctx: StageContext) -> dict:
        """The settings subset this stage's output actually depends on —
        persisted so a later resume can tell whether the user changed
        something that invalidates these candidates."""
        perf = ctx.settings.performance
        return {
            "clips": ctx.settings.clips.__dict__.copy(),
            "curve": ctx.settings.curve.__dict__.copy(),
            # Which detector found the shot cuts, and how sensitively —
            # a different cut list is a different scenes channel.
            "scenes": {
                "fast": perf.fast_scene_detect,
                "threshold": perf.scene_threshold,
                "height": perf.scene_height,
            },
        }

    def artifacts_ok(self, ctx: StageContext, data: dict) -> bool:
        # Window lengths, channel weights and the scene detector all change
        # WHICH moments get picked, so a change must re-extract rather than
        # reuse stale candidates. Compared leniently against factory defaults
        # so adding a setting never discards work the user didn't invalidate.
        from ..jobs.queue import fingerprint_ok

        factory = self._settings_used(
            _FactoryCtx(config.Settings())  # type: ignore[arg-type]
        )
        return fingerprint_ok(data.get("settings_used"), self._settings_used(ctx), factory)

    def run(self, ctx: StageContext) -> dict:
        import numpy as np

        from . import curve as curve_mod
        from . import windows as windows_mod

        prior = ctx.prior or {}
        ingest = prior.get("ingest")
        diarize = prior.get("diarize")
        events = prior.get("events")
        if not (ingest and diarize and events):
            raise StageError("Candidates need ingest + diarize + events outputs.")

        segments = diarize["segments"]
        duration = float(ingest["probe"]["duration_sec"])
        n = int(np.ceil(duration))

        curves_path = Path(events["curves_path"])
        if not curves_path.exists():
            raise StageError("curves.json missing — re-run events.")
        curves = json.loads(curves_path.read_text())

        ctx.emit(-1, "Detecting scene changes…")
        emit_scene = lambda f: ctx.emit(f * 0.6, "Detecting scene changes…")  # noqa: E731
        perf = ctx.settings.performance
        scene_times: list[float] | None = None
        if perf.fast_scene_detect:
            scene_times = detect_scenes_ffmpeg(
                ingest["media_path"],
                threshold=perf.scene_threshold,
                height=perf.scene_height,
                progress=emit_scene,
            )
            if scene_times is None:
                ctx.emit(-1, "Fast scene detection unavailable — falling back…")
        if scene_times is None:
            try:
                scene_times = detect_scenes(ingest["media_path"], progress=emit_scene)
            except Exception:  # noqa: BLE001 — scenes are a minor channel; degrade
                scene_times = []
        (ctx.job_dir / "scenes.json").write_text(json.dumps(scene_times))

        ctx.emit(0.6, "Building interest curve…")
        channels = {
            "heatmap": curve_mod.heatmap_channel(ingest.get("heatmap"), n),
            "dynamics": curve_mod.dynamics_channel(curves["dynamics"], curves["grid_sec"], n),
            "events": curve_mod.events_channel(events["timeline"], n),
            "turns": curve_mod.turns_channel(diarize["turns"], n),
            "arousal": curve_mod.arousal_channel(
                curves.get("arousal", []), curves.get("arousal_grid_sec", 0.5), n
            ),
            "scenes": curve_mod.scenes_channel(scene_times, n),
            "lexical": curve_mod.lexical_channel(segments, n),
        }
        curve, effective_weights = curve_mod.interest_curve(
            channels, ctx.settings.curve.__dict__
        )

        ctx.emit(0.8, "Extracting candidate windows…")
        candidates = windows_mod.extract(
            curve, channels, segments, duration, ctx.settings.clips
        )
        if not candidates:
            raise StageError(
                "No candidate moments found — the video may be too short or too quiet."
            )

        # Persist the curve for the review UI's timeline visualization.
        (ctx.job_dir / "interest_curve.json").write_text(
            json.dumps({"per_sec": np.round(curve, 4).tolist()})
        )

        return {
            "candidates": [c.to_json() for c in candidates],
            "count": len(candidates),
            "effective_weights": effective_weights,
            "scene_count": len(scene_times),
            "heatmap_present": bool(ingest.get("heatmap")),
            "settings_used": self._settings_used(ctx),
        }
