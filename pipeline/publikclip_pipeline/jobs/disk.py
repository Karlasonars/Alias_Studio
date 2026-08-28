"""Pre-flight disk space check (E1-F07 / T-12).

Before any stage writes, estimate what THIS job still needs to put on disk,
charge each piece to the volume it actually lands on, and compare with what
is free there. A job writes to up to three places that are routinely the
same drive but do not have to be: the job dir (PUBLIKCLIP_HOME/jobs),
the model caches (PUBLIKCLIP_HOME/models by default, but HF_HOME and
TORCH_HOME can point the two foreign caches anywhere), and bin/ for the
static ffmpeg. The system temp dir is deliberately NOT checked: the only
pipeline writes there are scenes.txt (a text file of cut timestamps) and
two probe .ass files — kilobytes, verified by grep, not worth a false
"disk full" on an unrelated volume.

Estimates are honest ranges, not numbers. The wav is exact arithmetic from
the source duration; a URL download uses yt-dlp's own filesize fields when
its format pick matches ours and widens to a bitrate range when it cannot
know; the rendered clips depend on content and encoder, so they are only
ever a range. Anything that cannot be sized at all is named in `unknown`
instead of being invented.

The policy, which is the part a reader actually needs:

- Block only on a CONFIDENT shortfall — free space below the LOW end of
  the estimate. In the gray zone between low and high the job starts with
  a warning; a false block costs the user a job they asked for, a false
  pass costs a failure the checkpoints already survive.
- A blocked job is marked 'failed' with the numbers in its error, never
  left 'pending': next_pending() serves pending jobs to the shell's
  auto-advance, so a pending-but-unstartable job would be respawned in a
  tight loop the moment its refusal exits. 'failed' lets the queue
  continue past it (jobs behind it on the same volume fail their own
  checks in seconds, each with the same actionable message, instead of
  waiting forever), and checkpoint resume makes retry nearly free once
  space is freed — the same recovery contract reconcile_stale_running()
  uses for interrupted jobs.
- Unknown never refuses (§5.9). A volume whose free space cannot be read
  degrades to a warning; a component that cannot be sized simply does not
  count against the disk. The check speaks only with evidence.

Passing the check does not remove the mid-run disk-full case, it makes it
rarer. When the disk fills anyway, behaviour is exactly what it was before
this module existed: registry downloads keep a resumable .part, the lazy
model path surfaces a raw OSError (T-13's catalogue territory), a failed
stage marks the job failed, and every completed checkpoint survives for
resume. Nothing here runs mid-download.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .. import config
from .. import setup as setup_mod

# The wav is exact: 16 kHz mono s16 (normalize.extract_analysis_audio).
AUDIO_BYTES_PER_SEC = config.AUDIO_SR * 2
WAV_HEADER_BYTES = 44

# Rendered 1080x1920 H.264 output. Content-dependent (a static podcast at
# CRF 19 sits near the low end, busy gameplay near the high), so these are
# range bounds for the UI, not contracts — the setup.py convention.
RENDER_BPS_LOW = 250_000
RENDER_BPS_HIGH = 1_200_000

# A <=1080p H.264+AAC source when yt-dlp cannot report its size.
URL_BPS_LOW = 150_000
URL_BPS_HIGH = 1_000_000

# media_cfr.mp4 vs its source: a CRF 18 re-encode of already-compressed
# footage can land either side of the original size.
CFR_LOW_RATIO = 0.5
CFR_HIGH_RATIO = 2.0

# Filling a volume to its last byte breaks the OS and every other app on
# it, so the warn threshold keeps this much slack above the high estimate.
HEADROOM_BYTES = 512 * 1024 * 1024


@dataclass(frozen=True)
class Need:
    """One thing the job will write: a size range charged to the volume
    `path` lives on."""

    label: str
    path: Path
    low: int
    high: int


def _existing_ancestor(path: Path) -> Path:
    p = Path(path)
    while not p.exists():
        parent = p.parent
        if parent == p:
            break
        p = parent
    return p


def volume_key(path: Path) -> str:
    """The drive a path lands on ('C:\\', or the UNC share root). Nearest
    existing ancestor first: the target dir may not exist yet."""
    p = _existing_ancestor(path)
    try:
        p = p.resolve()
    except OSError:
        pass
    return p.anchor or str(p)


def free_bytes(path: Path) -> int | None:
    """Free bytes on the path's volume, or None when the answer does not
    exist — a network drive, an odd filesystem, a permission quirk. None is
    a legitimate answer, not an error (§5.9)."""
    try:
        return shutil.disk_usage(_existing_ancestor(path)).free
    except OSError:
        return None


def wav_need(duration_sec: float) -> int:
    return int(duration_sec * AUDIO_BYTES_PER_SEC) + WAV_HEADER_BYTES


def clips_need(clips: "config.ClipSettings") -> tuple[int, int]:
    low = int(clips.select_count * clips.target_len * RENDER_BPS_LOW)
    high = int(clips.select_count * clips.max_len * RENDER_BPS_HIGH)
    return low, high


def url_source_need(raw: dict, duration_sec: float) -> tuple[int, int]:
    """Size range for a URL download, from what yt-dlp's -J call already
    learned (UrlMeta.raw carries the whole info dict).

    The reported filesize fields describe yt-dlp's DEFAULT format pick,
    which our capped DOWNLOAD_FORMAT only matches up to MAX_HEIGHT: for a
    4K source the report is an upper bound on what we will actually fetch,
    so it may only serve as the HIGH end there, with the low end falling
    back to the duration heuristic.
    """
    total = 0
    heights: list[int] = []
    reqs = raw.get("requested_formats")
    if isinstance(reqs, list) and reqs:
        for fmt in reqs:
            if not isinstance(fmt, dict):
                continue
            size = fmt.get("filesize") or fmt.get("filesize_approx")
            if not size:
                total = 0
                break
            total += int(size)
            if isinstance(fmt.get("height"), (int, float)) and fmt["height"]:
                heights.append(int(fmt["height"]))
    if not total:
        size = raw.get("filesize") or raw.get("filesize_approx")
        if size:
            total = int(size)
            if isinstance(raw.get("height"), (int, float)) and raw["height"]:
                heights = [int(raw["height"])]
    heuristic = (int(duration_sec * URL_BPS_LOW), int(duration_sec * URL_BPS_HIGH))
    if not total:
        return heuristic
    if heights and max(heights) > config.MAX_HEIGHT:
        return (heuristic[0], total)
    return (int(total * 0.9), int(total * 1.1))


def gather(job, settings: "config.Settings") -> tuple[list[Need], list[str]]:
    """Everything this job still needs to write, minus what is already on
    disk — which is what makes a resume after freeing space pass without
    re-demanding the media it already downloaded. Every probe in here
    degrades to an `unknown` entry instead of raising: the check must never
    be the thing that breaks a job (§5.9)."""
    from ..ingest import normalize, ytdlp

    needs: list[Need] = []
    unknown: list[str] = []

    try:
        status = setup_mod.status(settings)
        for item in status["items"]:
            if item["present"]:
                continue
            if item["bytes"] is None:
                unknown.append(f"{item['label']} (size depends on this machine)")
            else:
                needs.append(
                    Need(item["label"], setup_mod.item_dir(item["id"]), item["bytes"], item["bytes"])
                )
    except Exception:  # noqa: BLE001 — a broken presence probe must not block a job
        unknown.append("model downloads")

    duration = None
    if job.source_type == "file":
        src = Path(job.source).expanduser()
        try:
            info = normalize.probe(src)
            duration = info.duration_sec
            if info.vfr and not (job.dir / "media_cfr.mp4").exists():
                size = src.stat().st_size
                needs.append(
                    Need(
                        "frame-rate normalization",
                        job.dir,
                        int(size * CFR_LOW_RATIO),
                        int(size * CFR_HIGH_RATIO),
                    )
                )
        except Exception:  # noqa: BLE001 — no ffprobe yet, or a broken file: ingest will say so
            unknown.append("source duration (could not probe the file)")
    else:
        media = job.dir / "media.mp4"
        if media.exists():
            try:
                duration = normalize.probe(media).duration_sec
            except Exception:  # noqa: BLE001
                unknown.append("source duration (could not probe the downloaded media)")
        else:
            try:
                # The same metadata call ingest makes minutes later; a few
                # seconds of network against a multi-GB download decision.
                meta = ytdlp.fetch_meta(job.source, lambda _f, _m: None)
                duration = meta.duration_sec
                low, high = url_source_need(meta.raw, duration)
                needs.append(Need("source download", job.dir, low, high))
            except Exception:  # noqa: BLE001 — offline or a dead URL: ingest reports it properly
                unknown.append("source size (could not fetch video metadata)")

    if not (job.dir / "audio16k.wav").exists():
        if duration:
            needs.append(Need("analysis audio", job.dir, wav_need(duration), wav_need(duration)))
        # duration unknown → already named in `unknown` above

    low, high = clips_need(settings.clips)
    needs.append(Need("rendered clips", job.dir, low, high))
    return needs, unknown


def _fmt(n: int) -> str:
    if n >= 1_000_000_000:
        return f"{n / 1e9:.1f} GB"
    return f"{max(1, round(n / 1e6))} MB"


def _range_text(low: int, high: int) -> str:
    if _fmt(low) == _fmt(high):
        return f"about {_fmt(high)}"
    return f"roughly {_fmt(low)}\u2013{_fmt(high)}"


def assess(
    needs: list[Need],
    unknown: list[str],
    free_fn: Callable[[Path], int | None] = free_bytes,
    volume_fn: Callable[[Path], str] = volume_key,
) -> dict:
    """Group the needs by volume, compare with free space, decide.
    free_fn/volume_fn are injectable so the two-volume policy is testable
    on a one-drive machine."""
    volumes: dict[str, dict] = {}
    for need in needs:
        key = volume_fn(need.path)
        vol = volumes.setdefault(
            key, {"volume": key, "free": free_fn(need.path), "low": 0, "high": 0}
        )
        vol["low"] += need.low
        vol["high"] += need.high

    action = "ok"
    lines: list[str] = []
    for vol in volumes.values():
        free = vol["free"]
        if free is None:
            action = "warn" if action == "ok" else action
            lines.append(
                f"Free space on {vol['volume']} could not be read — "
                "continuing without a disk check there."
            )
        elif free < vol["low"]:
            action = "block"
            lines.append(
                f"Not enough disk space: this job needs {_range_text(vol['low'], vol['high'])} "
                f"free on {vol['volume']} and only {_fmt(free)} is free."
            )
        elif free < vol["high"] + HEADROOM_BYTES:
            action = "warn" if action == "ok" else action
            lines.append(
                f"Disk space is tight: this job may need up to {_fmt(vol['high'])} "
                f"on {vol['volume']} and {_fmt(free)} is free."
            )
    if action == "block":
        lines.append("Nothing was written — free up space and resume this job from the rail.")
        if unknown:
            lines.append("Not counted (size unknown): " + "; ".join(unknown) + ".")
    return {
        "action": action,
        "message": " ".join(lines),
        "volumes": list(volumes.values()),
        "unknown": unknown,
    }


def preflight(job) -> dict:
    settings = config.Settings.from_json(json.loads(job.settings_json))
    needs, unknown = gather(job, settings)
    return assess(needs, unknown)


def block_start(job, report: dict) -> None:
    """What 'cannot start' means for the queue: the job becomes 'failed'
    with the numbers in its error. Never 'pending' — see the module
    docstring for why that would spawn-loop — and never deleted: the row,
    the settings snapshot and every checkpoint survive, so a resume after
    freeing space continues exactly where the job stood."""
    from . import queue

    queue.set_job_status(job.id, "failed", report["message"])
