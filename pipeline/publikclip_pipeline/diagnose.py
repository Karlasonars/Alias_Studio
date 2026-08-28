"""The diagnostic bundle (E14-F03 / T-15).

A beta user's bug report is only as good as the file they can safely send,
and they will only send a file they can read and trust. So the bundle is a
plain zip of pretty-printed JSON plus a README that says what is inside
and what was removed â€” inspectable with any zip tool before it leaves the
machine â€” and it is built ALLOWLIST-FIRST: nothing enters it except what
MANIFEST declares, and a test walks a built bundle to enforce that a
future addition must be declared here rather than slipping in.

Four things never enter, by construction rather than by scrubbing:

  - API keys and tokens â€” every serialized file passes through
    errors.redact() (T-13's one redaction implementation; extended, never
    duplicated), which strips stored secrets, key shapes, credentialed
    query params and the home directory.
  - file paths â€” no field carries one; the checkpoint listing uses stage
    names, the disk line uses volume anchors.
  - media and anything transcript-shaped â€” checkpoint DATA is never
    copied. asr/diarize/score/candidates contribute counts and scalar
    flags only; the user's words do not ride along "because they might
    help".
  - the user's content identity â€” the source URL/path, the video title
    and the media filename are stripped LITERALLY via redact()'s `extra`
    terms wherever they might appear (an error cause like "File not
    found: ~/x.mp4" included), and the settings snapshot's two
    user-authored prose fields (titles/descriptions keywords) are masked.
    Somebody cutting unreleased footage must be able to send a bundle
    that does not name it. What replaces them is shape: source_type plus
    the probe (duration, resolution, fps, VFR, codec, audio) â€” the
    content-neutral half that actually diagnoses.

There are no persisted app logs to include (nothing writes one today);
error.json's detail â€” the redacted traceback/stderr of the failure â€” is
the closest thing and is included when present. No network, no upload:
the user sends the file themselves (E14-F04 is deliberately not this).
"""

from __future__ import annotations

import json
import platform
import time
import zipfile
from pathlib import Path

from . import config, errors, hardware_profile, setup
from .jobs import disk as disk_mod
from .jobs import queue

BUNDLE_FORMAT = 1

# Every file the bundle may contain, and for the curated ones, every key
# (at any depth) their JSON may use. Copied-through documents are marked
# "*": settings.json is the job's own snapshot (schema-guarded elsewhere,
# prose fields masked below), error.json is T-13's already-redacted value,
# hardware.json is the measured profile. test_diagnose.py enforces this.
MANIFEST: dict[str, set[str] | str] = {
    "README.txt": "*",
    "manifest.json": {
        "bundle_format", "created_at", "pipeline_version", "os", "python",
    },
    "job.json": {
        "id", "created_at", "status", "error", "source_type", "probe",
        "duration_sec", "width", "height", "fps", "vfr", "start_time",
        "video_codec", "has_audio",
    },
    "stages.json": set(hardware_profile.STAGES) | {
        "status", "seconds", "error", "checkpoint", "schema_version",
        "checkpoint_bytes",
    },
    "results.json": {
        "asr", "language", "model", "compute_type", "device", "align_device",
        "candidates", "count", "scene_count", "heatmap_present",
        "score", "llm_mode", "scored_count", "t2_ran", "scoring_config_version",
        "render", "outputs", "kept_from_editor", "emoji_ok", "captions_burned",
    },
    "models.json": {
        "items", "id", "label", "bytes", "present", "total_missing_bytes",
    },
    "disk.json": {"volume", "free_bytes"},
    "settings.json": "*",
    "error.json": "*",
    "hardware.json": "*",
}

_README = """This is an Alias Studio diagnostic bundle.

Every file is plain JSON â€” open them with any text editor and read
everything before you send it. What was removed before writing:

  - API keys, tokens and anything shaped like one   -> [redacted]
  - your home directory in any path                 -> ~
  - the video's source URL/path, its title and its
    filename, plus your keyword settings            -> [removed]
  - transcripts, media, and checkpoint contents were never copied at all

What each file is:
  manifest.json  which build, which OS
  job.json       the job's status and the SHAPE of its source (duration,
                 resolution, fps, codec) â€” not the source itself
  stages.json    per-stage status, measured seconds, checkpoint presence
  results.json   content-neutral counters (clips scored, clips rendered)
  models.json    which models are present on this machine
  disk.json      free space on the volume jobs write to
  settings.json  the settings this job actually ran with
  error.json     the described failure, if the job failed (redacted when
                 it was written)
  hardware.json  the measured hardware profile
"""


def _content_terms(job: queue.Job, ingest_data: dict) -> list[str]:
    """The job's known content identifiers, stripped literally wherever
    they appear â€” the same mechanism redact() uses for stored secrets."""
    terms = [job.source, job.title or ""]
    media_path = str(ingest_data.get("media_path") or "")
    if media_path:
        terms.append(media_path)
        terms.append(Path(media_path).name)
    if job.source:
        terms.append(Path(job.source).name)
    terms.append(str(ingest_data.get("title") or ""))
    # The terms are matched against SERIALIZED json, where a backslashed
    # path appears escaped â€” so each term also contributes its
    # json-escaped and forward-slashed spellings.
    expanded = set()
    for term in terms:
        if not term or len(term) < 3:
            continue
        expanded.add(term)
        expanded.add(term.replace("\\", "\\\\"))
        expanded.add(term.replace("\\", "/"))
    # Longest first, so "x.mp4" cannot break "~/videos/x.mp4" mid-replace.
    return sorted(expanded, key=len, reverse=True)


def _checkpoint_data(job: queue.Job, stage: str) -> dict:
    try:
        envelope = json.loads(queue.checkpoint_path(job, stage).read_text(encoding="utf-8"))
        data = envelope.get("data")
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return {}


def _stages_file(job: queue.Job) -> dict:
    with queue._connect() as conn:  # noqa: SLF001 â€” same package, one reader
        rows = conn.execute(
            "SELECT stage, status, started_at, finished_at, error FROM stage_runs"
            " WHERE job_id = ?",
            (job.id,),
        ).fetchall()
    by_stage = {r["stage"]: r for r in rows}
    out: dict[str, dict] = {}
    for name in hardware_profile.STAGES:
        row = by_stage.get(name)
        path = queue.checkpoint_path(job, name)
        entry: dict = {
            "status": row["status"] if row else None,
            "seconds": (
                round(row["finished_at"] - row["started_at"], 1)
                if row and row["finished_at"] is not None
                else None
            ),
            "error": row["error"] if row else None,
            "checkpoint": path.exists(),
        }
        if path.exists():
            try:
                envelope = json.loads(path.read_text(encoding="utf-8"))
                entry["schema_version"] = envelope.get("schema_version")
                entry["checkpoint_bytes"] = path.stat().st_size
            except (OSError, json.JSONDecodeError, UnicodeDecodeError):
                pass
        out[name] = entry
    return out


def _results_file(job: queue.Job) -> dict:
    """Counters and scalar flags from the checkpoints â€” never their data.
    Each key here is declared in MANIFEST; the transcripts, windows and
    clip contents those checkpoints hold are exactly what must not ride."""
    asr = _checkpoint_data(job, "asr")
    cands = _checkpoint_data(job, "candidates")
    score = _checkpoint_data(job, "score")
    render = _checkpoint_data(job, "render")
    return {
        "asr": {
            k: asr.get(k) for k in ("language", "model", "compute_type", "device", "align_device")
        },
        "candidates": {
            "count": cands.get("count"),
            "scene_count": cands.get("scene_count"),
            "heatmap_present": cands.get("heatmap_present"),
        },
        "score": {
            "llm_mode": score.get("llm_mode"),
            "model": score.get("model"),
            "scored_count": score.get("scored_count"),
            "t2_ran": score.get("t2_ran"),
            "scoring_config_version": score.get("scoring_config_version"),
        },
        "render": {
            "outputs": len(render.get("outputs") or []),
            "kept_from_editor": len(render.get("kept_from_editor") or []),
            "emoji_ok": render.get("emoji_ok"),
            "captions_burned": render.get("captions_burned"),
        },
    }


def _masked_settings(job: queue.Job) -> dict:
    """The snapshot the job actually ran with â€” reproduction gold â€” minus
    its two user-authored prose fields, which can name the content."""
    try:
        data = json.loads(job.settings_json)
    except json.JSONDecodeError:
        return {}
    for group in ("titles", "descriptions"):
        section = data.get(group)
        if isinstance(section, dict) and section.get("keywords"):
            section["keywords"] = "[removed]"
    return data


def build_bundle(job: queue.Job, out_path: Path | None = None) -> dict:
    """Build the zip; returns {"path", "files"}. Every file's serialized
    text passes through errors.redact() with the job's content terms â€”
    the one redaction implementation, parameterized, never a second."""
    ingest = _checkpoint_data(job, "ingest")
    terms = _content_terms(job, ingest)

    error_payload = None
    error_file = job.dir / queue.ERROR_FILE
    if error_file.exists():
        try:
            error_payload = json.loads(error_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            error_payload = None

    probe = ingest.get("probe") or {}
    files: dict[str, object] = {
        "manifest.json": {
            "bundle_format": BUNDLE_FORMAT,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "pipeline_version": _pipeline_version(),
            "os": platform.platform(),
            "python": platform.python_version(),
        },
        "job.json": {
            "id": job.id,
            "created_at": job.created_at,
            "status": job.status,
            "error": job.error,
            "source_type": job.source_type,
            "probe": {
                k: probe.get(k)
                for k in (
                    "duration_sec", "width", "height", "fps", "vfr",
                    "start_time", "video_codec", "has_audio",
                )
            },
        },
        "stages.json": _stages_file(job),
        "results.json": _results_file(job),
        "models.json": setup.status(),
        "disk.json": {
            "volume": disk_mod.volume_key(config.home_dir()),
            "free_bytes": disk_mod.free_bytes(config.home_dir()),
        },
        "settings.json": _masked_settings(job),
        "hardware.json": hardware_profile.load(),
    }
    if error_payload is not None:
        files["error.json"] = error_payload

    out = out_path or (job.dir / f"diagnostic-{job.id}.zip")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("README.txt", _README)
        for name, payload in files.items():
            text = json.dumps(payload, indent=1, ensure_ascii=False)
            zf.writestr(name, errors.redact(text, extra=terms))
    return {"path": str(out), "files": ["README.txt", *files.keys()]}


def _pipeline_version() -> str:
    try:
        from importlib.metadata import version

        return version("publikclip-pipeline")
    except Exception:  # noqa: BLE001 â€” a missing dist must not block a bug report
        return "unknown"
