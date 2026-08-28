"""SQLite-backed job store with per-stage checkpoints.

Design (PLAN.md §3): artifacts on disk are the truth; the DB is bookkeeping.
A stage is complete iff its DB row says done AND its checkpoint JSON exists
with the current schema_version. Kill the process at any point and `resume`
re-runs only the stages whose checkpoints are missing or stale.

Checkpoint files live at <job_dir>/<stage>.json as an envelope:

    {"stage": ..., "schema_version": ..., "created_at": ..., "data": {...}}

Writes are atomic (tmp + rename) so a crash mid-write never leaves a
half-checkpoint that resume would trust.
"""

from __future__ import annotations

import json
import sqlite3
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

from .. import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    created_at REAL NOT NULL,
    source_type TEXT NOT NULL,          -- 'url' | 'file'
    source TEXT NOT NULL,
    title TEXT,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending|running|done|failed|cancelled
    error TEXT,
    settings_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS stage_runs (
    job_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    status TEXT NOT NULL,               -- running|done|failed
    schema_version INTEGER NOT NULL,
    started_at REAL NOT NULL,
    finished_at REAL,
    error TEXT,
    PRIMARY KEY (job_id, stage)
);
"""


@dataclass
class Job:
    id: str
    created_at: float
    source_type: str
    source: str
    title: str | None
    status: str
    error: str | None
    settings_json: str

    @property
    def dir(self) -> Path:
        return config.jobs_dir() / self.id


def _connect() -> sqlite3.Connection:
    config.ensure_home()
    conn = sqlite3.connect(config.db_path(), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _row_to_job(row: sqlite3.Row) -> Job:
    return Job(
        id=row["id"],
        created_at=row["created_at"],
        source_type=row["source_type"],
        source=row["source"],
        title=row["title"],
        status=row["status"],
        error=row["error"],
        settings_json=row["settings_json"],
    )


def create_job(source_type: str, source: str, settings_json: str) -> Job:
    if source_type not in ("url", "file"):
        raise ValueError(f"bad source_type {source_type!r}")
    job_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    with _connect() as conn:
        conn.execute(
            "INSERT INTO jobs (id, created_at, source_type, source, status, settings_json)"
            " VALUES (?, ?, ?, ?, 'pending', ?)",
            (job_id, time.time(), source_type, source, settings_json),
        )
    job = get_job(job_id)
    assert job is not None
    job.dir.mkdir(parents=True, exist_ok=True)
    # Snapshot settings into the job dir so resume never picks up new defaults.
    _atomic_write_json(job.dir / "settings.json", json.loads(settings_json))
    return job


def update_settings(job_id: str, settings_json: str) -> Job | None:
    """Change a job's settings in BOTH places that hold them.

    A job's settings live in the DB row (what run_stages reads) and in
    <job_dir>/settings.json (what the per-clip edit path reads). Writing only
    one of them splits the job's own state: a restyle would re-render the
    clips correctly from the DB while the clip editor kept showing — and
    re-rendering with — the pre-restyle values, silently undoing the restyle
    for any clip touched afterwards. Both, or neither.
    """
    with _connect() as conn:
        conn.execute("UPDATE jobs SET settings_json = ? WHERE id = ?", (settings_json, job_id))
    job = get_job(job_id)
    if job is not None:
        job.dir.mkdir(parents=True, exist_ok=True)
        _atomic_write_json(job.dir / "settings.json", json.loads(settings_json))
    return job


def get_job(job_id: str) -> Job | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return _row_to_job(row) if row else None


def list_jobs(limit: int = 50) -> list[Job]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [_row_to_job(r) for r in rows]


def set_job_status(job_id: str, status: str, error: str | None = None, title: str | None = None) -> None:
    with _connect() as conn:
        if title is not None:
            conn.execute(
                "UPDATE jobs SET status = ?, error = ?, title = ? WHERE id = ?",
                (status, error, title, job_id),
            )
        else:
            conn.execute(
                "UPDATE jobs SET status = ?, error = ? WHERE id = ?", (status, error, job_id)
            )


# ---------------------------------------------------------------------------
# Cancellation (T-07 / E2-F07)
#
# Two sentinel files in the job dir carry the cancel protocol, and their
# ownership is deliberately split across two processes — do not "tidy" one
# half without the other (main.rs carries the matching comment):
#
#   cancel.requested — written by the Rust shell (cancel_job), consumed
#       here: run_stages exits at the next stage boundary, and deletes any
#       stale copy when a run starts, so resuming a hard-killed job cannot
#       cancel itself.
#   cancelled — the library's marker. list_job_dirs (main.rs) reads the
#       filesystem, not SQLite, so this file is what makes 'cancelled'
#       visible there. Written by whichever side knows first: this module
#       at a boundary, the shell right after a hard kill — which keeps the
#       library correct even if the bookkeeping one-shot never runs.
#       Deleted here when a run starts.

CANCEL_FLAG = "cancel.requested"
CANCELLED_MARKER = "cancelled"
# The described failure (errors.ErrorInfo), written on any stage failure,
# redacted at write time. Disk truth for the ErrorPanel, T-14's
# resume-from-stage, and T-15's diagnostic bundle.
ERROR_FILE = "error.json"


def _record_failure(job: Job, stage: "Stage", err: BaseException) -> None:
    """The choke point (T-13): every stage failure becomes one described,
    redacted ErrorInfo — the DB row gets the human cause (never a repr),
    the job dir gets the full structured value."""
    from .. import errors

    info = errors.describe(err, stage=stage.name)
    mark_stage(job.id, stage.name, "failed", stage.schema_version, info.cause)
    set_job_status(job.id, "failed", f"{stage.name}: {info.cause}")
    try:
        _atomic_write_json(job.dir / ERROR_FILE, info.to_json())
    except OSError:
        # A disk too broken to hold error.json must not mask the original
        # failure (§5.9) — the DB row above still carries the cause.
        pass


class JobCancelled(Exception):  # noqa: N818 - a signal, not an error
    """A cancel request landed at a stage boundary. Deliberate, not a
    failure: the CLI exits 0 on this, so the shell's crash handler ('exited')
    never fires for a cancel."""


def _mark_cancelled_on_disk(job: Job) -> None:
    set_job_status(job.id, "cancelled")
    (job.dir / CANCELLED_MARKER).write_text("1", encoding="utf-8")
    (job.dir / CANCEL_FLAG).unlink(missing_ok=True)


def next_pending() -> Job | None:
    """The queue's entire scheduling policy, in one query (T-08 / E2-F04).

    Eligible means status 'pending' and nothing else, ever: failed is
    terminal (no automatic retry - an unattended retry of a 40-minute GPU
    job is a real cost, and checkpoint resume makes manual retry nearly
    free), cancelled never comes back, running is the shell's business.
    Order is FIFO; rowid breaks created_at ties, which on Windows can land
    inside the same clock tick for jobs enqueued back to back.

    The Rust side deliberately holds no copy of this policy - it asks this
    function (via `jobs next`) and spawns whatever it answers.
    """
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM jobs WHERE status = 'pending'"
            " ORDER BY created_at ASC, rowid ASC LIMIT 1"
        ).fetchone()
    return _row_to_job(row) if row else None


def cancel_pending(job_id: str) -> dict:
    """Cancel a job that has not started. Guarded on 'pending' the way
    mark_cancelled guards on 'running': the active job's cancel is T-07's
    kill path, and a finished job is not this function's to touch."""
    job = get_job(job_id)
    if job is None:
        return {"marked": False, "status": None}
    if job.status != "pending":
        return {"marked": False, "status": job.status}
    _mark_cancelled_on_disk(job)
    return {"marked": True, "status": "cancelled"}


def reconcile_stale_running() -> list[dict]:
    """App-start reconciliation: a 'running' row when no app is running is
    a ghost - the app is the runner, so at startup nothing can truly be
    running. Only 'running' rows are touched; that is what makes
    resurrection impossible (a cancelled job is not 'running', a pending
    job stays queued across the restart).

    A ghost whose job dir carries the cancelled marker becomes 'cancelled' -
    disk truth, and it heals the case where T-07's bookkeeping one-shot
    never ran. Everything else becomes 'failed' with an error that says
    what actually happened. 'failed' is mildly wrong as a label for an
    interrupted job and deliberately so: an 'interrupted' status would be
    enum creep with a single consumer. Do not sniff this error string to
    re-derive the distinction; if a view ever needs it rendered apart,
    promote a real status instead.
    """
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM jobs WHERE status = 'running'").fetchall()
    out: list[dict] = []
    for job in (_row_to_job(r) for r in rows):
        if (job.dir / CANCELLED_MARKER).exists():
            set_job_status(job.id, "cancelled")
            out.append({"job_id": job.id, "status": "cancelled"})
        else:
            set_job_status(
                job.id,
                "failed",
                "interrupted: the app closed while this job was running - "
                "resume to continue from its last checkpoint",
            )
            out.append({"job_id": job.id, "status": "failed"})
    return out


def mark_cancelled(job_id: str) -> dict:
    """Post-mortem bookkeeping after the shell hard-kills a run.

    Only a 'running' job can become cancelled: a cancel click racing the
    job's own completion must leave 'done' alone (the shell then removes the
    marker it optimistically wrote). Returns {"marked", "status"} so the
    shell can tell those cases apart.
    """
    job = get_job(job_id)
    if job is None:
        return {"marked": False, "status": None}
    if job.status != "running":
        return {"marked": False, "status": job.status}
    _mark_cancelled_on_disk(job)
    try:
        _drop_corrupt_render_outputs(job)
    except Exception as err:  # noqa: BLE001 - cleanup is best-effort (5.9):
        # the status write above must stand even on a machine whose ffprobe
        # is unavailable; skipping cleanup merely reverts to the pre-existing
        # exists()-only artifacts_ok behaviour this narrows.
        sys.stderr.write(f"cancel cleanup skipped: {err!r}\n")
    return {"marked": True, "status": "cancelled"}


def _drop_corrupt_render_outputs(job: Job) -> None:
    """Delete render outputs the killed run left truncated — the file,
    never the checkpoint.

    A kill mid-encode can truncate an mp4 that an older, still-valid render
    checkpoint lists; if the user then resumes with settings matching that
    checkpoint, artifacts_ok's exists() would serve the truncated file as
    done. Deleting the file routes through machinery that already exists:
    artifacts_ok fails (a listed path is gone) so the stage re-runs, while
    _previous_outputs keeps its adoption map for every clip whose file
    verified — per-file invalidation with no checkpoint surgery. Pruning
    checkpoint entries instead would let artifacts_ok pass with a clip
    missing.

    Only files the killed run was re-encoding from job settings can fail the
    probe: editor-kept clips are never open for writing here, so nothing the
    editor produced gets deleted.
    """
    if stage_statuses(job.id).get("render") != "running":
        return
    path = checkpoint_path(job, "render")
    if not path.exists():
        return
    try:
        envelope = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return
    outputs = (envelope.get("data") or {}).get("outputs") or []
    from ..render.renderer import verify_output  # deferred: no ffmpeg tax elsewhere

    for entry in outputs:
        if not isinstance(entry, dict) or entry.get("duration") is None:
            continue
        out = Path(str(entry.get("path", "")))
        if not out.name or not out.exists():
            continue
        if not verify_output(out, float(entry["duration"]))["ok"]:
            out.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Checkpoints


def _atomic_write_json(path: Path, payload: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def checkpoint_path(job: Job, stage: str) -> Path:
    return job.dir / f"{stage}.json"


def write_checkpoint(job: Job, stage: str, schema_version: int, data: dict) -> None:
    envelope = {
        "stage": stage,
        "schema_version": schema_version,
        "created_at": time.time(),
        "data": data,
    }
    _atomic_write_json(checkpoint_path(job, stage), envelope)
    with _connect() as conn:
        conn.execute(
            "INSERT INTO stage_runs (job_id, stage, status, schema_version, started_at, finished_at)"
            " VALUES (?, ?, 'done', ?, ?, ?)"
            " ON CONFLICT(job_id, stage) DO UPDATE SET"
            "   status='done', schema_version=excluded.schema_version,"
            "   finished_at=excluded.finished_at, error=NULL",
            (job.id, stage, schema_version, time.time(), time.time()),
        )


def read_checkpoint(job: Job, stage: str, schema_version: int) -> dict | None:
    """Return the stage's data dict iff a checkpoint with the expected
    schema_version exists and parses. Anything else means 're-run me'."""
    path = checkpoint_path(job, stage)
    if not path.exists():
        return None
    try:
        envelope = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None
    if envelope.get("schema_version") != schema_version:
        return None
    data = envelope.get("data")
    return data if isinstance(data, dict) else None


def mark_stage(job_id: str, stage: str, status: str, schema_version: int, error: str | None = None) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO stage_runs (job_id, stage, status, schema_version, started_at, error)"
            " VALUES (?, ?, ?, ?, ?, ?)"
            " ON CONFLICT(job_id, stage) DO UPDATE SET"
            "   status=excluded.status, schema_version=excluded.schema_version,"
            "   error=excluded.error,"
            "   started_at=CASE WHEN excluded.status='running' THEN excluded.started_at ELSE stage_runs.started_at END,"
            "   finished_at=CASE WHEN excluded.status='running' THEN NULL ELSE ? END",
            (job_id, stage, status, schema_version, time.time(), error, time.time()),
        )


def stage_statuses(job_id: str) -> dict[str, str]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT stage, status FROM stage_runs WHERE job_id = ?", (job_id,)
        ).fetchall()
    return {r["stage"]: r["status"] for r in rows}


# ---------------------------------------------------------------------------
# Stage runner


class StageError(Exception):
    """A stage failed in a way the user can act on. Message is user-facing.

    `code` names an entry in errors.CATALOG so the UI can attach actions
    and a docs link; sites without one still honour the contract — their
    message becomes the cause and the generic actions apply (T-13).
    `detail` carries technical text (an ffmpeg stderr tail) that belongs
    behind the UI's disclosure, never in the headline."""

    def __init__(self, message: str, *, code: str | None = None, detail: str | None = None):
        super().__init__(message)
        self.code = code
        self.detail = detail


ProgressFn = Callable[[str, float, str], None]  # (stage, fraction 0..1 or -1, message)


@dataclass
class StageContext:
    job: Job
    settings: "config.Settings"
    progress: ProgressFn

    @property
    def job_dir(self) -> Path:
        return self.job.dir

    def emit(self, fraction: float, message: str, stage: str = "") -> None:
        self.progress(stage, fraction, message)


def fingerprint_ok(stored: Any, current: Any, factory: Any) -> bool:
    """Compare a stage's persisted settings fingerprint against the current one.

    The naive comparison (`stored == current`) is wrong the moment a new
    setting is added: every checkpoint written before it exists lacks the
    key, mismatches, and throws away work that is still perfectly valid —
    an hour of transcription discarded because someone added an unrelated
    toggle.

    So a key missing from `stored` is compared against the FACTORY default
    instead. If the user never touched that setting, the old checkpoint is
    genuinely still correct and survives; if they did change it, the
    checkpoint really is stale and re-runs. Keys present on both sides are
    compared directly, nested dicts recursively.
    """
    if not isinstance(current, dict):
        return stored == current
    if not isinstance(stored, dict):
        return False
    for key, value in current.items():
        fac = factory.get(key) if isinstance(factory, dict) else None
        if key in stored:
            if not fingerprint_ok(stored[key], value, fac):
                return False
        elif value != fac:
            return False
    return True


class Stage:
    """Subclass contract: set `name` + `schema_version`, implement run().

    run() returns a JSON-serializable dict; the runner checkpoints it. A stage
    that also produces file artifacts must verify them in artifacts_ok() so a
    deleted media file invalidates the checkpoint even when the JSON survives.
    """

    name: str = ""
    schema_version: int = 1

    def run(self, ctx: StageContext) -> dict:  # pragma: no cover - interface
        raise NotImplementedError

    def artifacts_ok(self, ctx: StageContext, data: dict) -> bool:
        return True


def run_stages(job: Job, stages: Iterable[Stage], progress: ProgressFn) -> dict[str, dict]:
    """Run stages in order, skipping fresh checkpoints. Returns stage→data.

    The pipeline is a linear chain — every stage consumes the outputs of the
    ones before it — so a stage that re-runs invalidates everything after it,
    regardless of what those stages' own checkpoints say. Without this
    cascade a settings change can recompute an upstream stage while a
    downstream stage happily serves output derived from the OLD upstream
    data (e.g. new candidate windows but stale scores, or a re-directed
    camera whose trajectories never reach a cached render). That silent
    mismatch is what makes a setting look like it "does nothing".
    """
    settings = config.Settings.from_json(json.loads(job.settings_json))
    ctx = StageContext(job=job, settings=settings, progress=progress)
    results: dict[str, dict] = {}
    upstream_stale = False
    # A stale cancel flag or marker from a previous (possibly hard-killed)
    # run must not cancel THIS run the moment it starts. Run setup, not a
    # change to resume's contract. error.json follows the same rule: its
    # consumers (the ErrorPanel, T-14's resume-from-stage) read it BETWEEN
    # failure and the next spawn — by the time this line runs, the resume
    # is already underway and what re-runs is the checkpoint contract's
    # decision, never this file's.
    (job.dir / CANCEL_FLAG).unlink(missing_ok=True)
    (job.dir / CANCELLED_MARKER).unlink(missing_ok=True)
    (job.dir / ERROR_FILE).unlink(missing_ok=True)
    set_job_status(job.id, "running")
    for stage in stages:
        # The guaranteed-clean cancel boundary: after the previous stage's
        # write_checkpoint, before anything about the next stage runs, so a
        # cancel can never invalidate finished work. The <3 s criterion is
        # met by the shell's hard kill, not by this check.
        if (job.dir / CANCEL_FLAG).exists():
            _mark_cancelled_on_disk(job)
            raise JobCancelled(job.id)
        cached = read_checkpoint(job, stage.name, stage.schema_version)
        if cached is not None and not upstream_stale and stage.artifacts_ok(ctx, cached):
            results[stage.name] = cached
            progress(stage.name, 1.0, "cached")
            continue
        upstream_stale = True  # this stage re-runs → everything after it is stale
        mark_stage(job.id, stage.name, "running", stage.schema_version)
        progress(stage.name, -1.0, "starting")
        try:
            data = stage.run(_ctx_for(ctx, stage.name, results))
        except StageError as err:
            _record_failure(job, stage, err)
            raise
        except Exception as err:  # noqa: BLE001 - record then re-raise
            # This arm used to store repr(err) — which is how
            # OSError(22, 'Invalid argument') ended up on a user's screen.
            # describe() turns the unknown into a legible shape; the repr
            # survives only inside error.json's detail field (T-13).
            _record_failure(job, stage, err)
            raise
        write_checkpoint(job, stage.name, stage.schema_version, data)
        results[stage.name] = data
        progress(stage.name, 1.0, "done")
    set_job_status(job.id, "done", None)
    return results


@dataclass
class _StageScopedContext(StageContext):
    stage_name: str = ""
    prior: dict[str, dict] | None = None

    def emit(self, fraction: float, message: str, stage: str = "") -> None:
        self.progress(stage or self.stage_name, fraction, message)


def _ctx_for(ctx: StageContext, stage_name: str, prior: dict[str, dict]) -> _StageScopedContext:
    return _StageScopedContext(
        job=ctx.job,
        settings=ctx.settings,
        progress=ctx.progress,
        stage_name=stage_name,
        prior=prior,
    )
