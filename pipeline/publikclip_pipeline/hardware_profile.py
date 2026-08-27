"""Persisted hardware profile + measured realtime ratios (E1-F03, E13-F01).

The timing data already existed before this module: stage_runs has carried
started_at/finished_at for every stage of every job, and nothing read it.
This module reads it, folds it into ~/.publikclip/hardware_profile.json,
and derives the one number the UI shows: "a 60 min video ≈ N min".

The trap this file exists to avoid: a realtime ratio measured on the GPU
is a lie on the CPU path, and the same machine changes - a driver update
breaks CUDA, PUBLIKCLIP_DEVICE=cpu forces a diagnosis run, an eGPU is
unplugged. So every measurement is keyed to the configuration it was
measured under (the §4 fingerprint idea applied to a profile), and a
measurement under one key is never served under another. A machine with
no measurements under its current key honestly has no estimate.

The shell reads the JSON file directly and never probes - probing means a
`uv run` one-shot plus, in the worst case, nvidia-smi's 20 s timeout, and
T-08 already demonstrated what polling that kind of call does. The file
is rewritten by python at the end of every successful job and by the
`publikclip hardware` verb; between writes the display is as fresh as the
last probe, and the next run re-measures regardless.
"""

from __future__ import annotations

import json
import os
import statistics
import time
from pathlib import Path

from . import config, hardware
from .jobs import queue

PROFILE_FILE = "hardware_profile.json"

# What defines "the configuration this was measured under". Included: the
# device decisions themselves - each one changes which code path runs and
# therefore how fast it is. Excluded: vram_gb (identity, not speed - the
# gpu name already names the card, and keying on a rounded float invites
# spurious splits) and forced (a CAUSE, not a configuration: forcing cpu
# already shows up as torch_device=cpu etc., and keying on it would split
# one identical configuration into two profiles).
KEY_FIELDS = (
    "torch_device",
    "gpu",
    "whisper_device",
    "whisper_compute",
    "onnx_providers",
    "cpu_threads",
)

# Keep in sync with cli._stages(). An estimate is only offered once every
# stage has at least one sample under the current key - a partial sum
# would silently understate, which is a fabricated number with extra steps.
STAGES = ("ingest", "asr", "diarize", "events", "candidates", "score", "camera", "render")

# Median of the last N samples per stage: the median so one pathological
# job (a source that hit a degenerate path) cannot own the estimate, the
# window so the profile adapts when the machine genuinely changes speed,
# and the cap so the file stays bounded.
MAX_SAMPLES = 5


def profile_key(summary: dict) -> str:
    parts = []
    for field in KEY_FIELDS:
        value = summary.get(field)
        if isinstance(value, list):
            value = ",".join(str(v) for v in value)
        parts.append(str(value))
    return "|".join(parts)


def profile_path() -> Path:
    return config.home_dir() / PROFILE_FILE


def load() -> dict:
    try:
        return json.loads(profile_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return {}


def _write(profile: dict) -> None:
    path = profile_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(profile, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def _estimate(measured: dict, key: str) -> tuple[float | None, int]:
    """(ratio, jobs) for one key. ratio = processing seconds per source
    second, summed over per-stage medians; None until every stage has a
    sample - no estimate is better than an invented one (§5.9)."""
    bucket = measured.get(key) or {}
    stages = bucket.get("stages") or {}
    total = 0.0
    for name in STAGES:
        samples = (stages.get(name) or {}).get("samples") or []
        if not samples:
            return None, int(bucket.get("jobs") or 0)
        total += statistics.median(samples)
    return round(total, 4), int(bucket.get("jobs") or 0)


def _refresh_summary(profile: dict) -> dict:
    summary = hardware.summary()
    key = profile_key(summary)
    profile["summary"] = summary
    profile["key"] = key
    ratio, jobs = _estimate(profile.get("measured") or {}, key)
    profile["estimate_ratio"] = ratio
    profile["estimate_jobs"] = jobs
    return profile


def refresh() -> dict:
    """Probe now, keep every measurement, rewrite the file. The
    `publikclip hardware` verb - and the honest way to notice that the
    configuration changed since the last job."""
    profile = _refresh_summary(load())
    _write(profile)
    return profile


def update_after_job(job_id: str, run_started: float) -> dict | None:
    """Fold one successful run's stage timings into the profile.

    Only stages whose row STARTED inside this run count: a resumed job
    serves earlier stages from checkpoints, and their stage_runs rows
    still hold timings measured under whatever configuration ran them -
    exactly the cross-key contamination the profile key exists to stop.
    """
    job = queue.get_job(job_id)
    if job is None:
        return None
    # Read the ingest envelope directly rather than via read_checkpoint:
    # that helper enforces a schema_version this module has no business
    # knowing, and the probe's duration stays valid across schema drift.
    try:
        envelope = json.loads(
            queue.checkpoint_path(job, "ingest").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    ingest = envelope.get("data") or {}
    source_sec = ((ingest.get("probe") or {}).get("duration_sec")) or 0
    if not source_sec or source_sec <= 0:
        return None
    with queue._connect() as conn:  # noqa: SLF001 - same package, one reader
        rows = conn.execute(
            "SELECT stage, started_at, finished_at FROM stage_runs"
            " WHERE job_id = ? AND status = 'done' AND finished_at IS NOT NULL"
            " AND started_at >= ?",
            (job_id, run_started),
        ).fetchall()
    if not rows:
        return None

    profile = load()
    summary = hardware.summary()
    key = profile_key(summary)
    measured = profile.setdefault("measured", {})
    bucket = measured.setdefault(key, {"stages": {}, "jobs": 0})
    for row in rows:
        if row["stage"] not in STAGES:
            continue
        ratio = max(0.0, (row["finished_at"] - row["started_at"]) / source_sec)
        samples = bucket["stages"].setdefault(row["stage"], {"samples": []})["samples"]
        samples.append(round(ratio, 4))
        del samples[:-MAX_SAMPLES]
    bucket["jobs"] = int(bucket.get("jobs") or 0) + 1
    bucket["updated_at"] = time.time()
    _refresh_summary(profile)
    _write(profile)
    return profile
