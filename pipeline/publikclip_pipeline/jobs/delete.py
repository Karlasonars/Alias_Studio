"""Deleting a finished job (T-30, E2-F01): the whole job, one at a time.

What "delete" means here: the job dir under PUBLIKCLIP_HOME/jobs/<id> —
source media, intermediates, checkpoints, rendered clips — and both of
its SQLite rows (`jobs`, `stage_runs`). Not "intermediates only": that is
E2-F06, a different task. Not bulk, not a trash, not by age (CLAUDE.md
§8). Everything that DECIDES lives here (§2: python decides, the shell
triggers): whether the job is terminal, what it costs, what was removed.
The one judgement the shell keeps is whether it is itself running or
rendering this job right now, which nothing else can see.

Only terminal jobs: done, failed, cancelled. Pending has cancel-pending;
running has T-07's kill. A dir with no SQLite row — the rail lists it
(list_job_dirs walks the filesystem), the queue does not — counts as
terminal: nothing this side can see is running it. Where such a dir
comes from: never from this code, which always writes the row before the
dir (queue.create_job) and refuses every other write without a row; it
comes from db.sqlite3 being deleted or replaced under an existing jobs/
folder, or a folder copied in by hand. Both real, both deletable.

Order of operations: files first, row last. The dir is removed with an
error collector, and the rows go only when the dir is fully gone. A
partial failure — on Windows, a clip held open by the Review player or
an Explorer preview — leaves the row intact and answers ok: false with a
message that names the job as only partly removed, so the rail keeps
showing what is still there and a retry finishes the job. An already-
missing dir is not an error: the rows go and the call succeeds.

The numbers in the confirmation are measured, not estimated: `bytes` is
the sum of the sizes of every file under the dir as it is on disk, and
`clips` is the number of entries in render.json's outputs — the rendered
videos the Review lists: clips, ranking montages, and a story job's one
file (D-20) alike.

Instagram links and calibration records (insights/calibration.py) are
KEPT, and the confirmation names them. `published_clips` is calibration
history: the fit replays the provenance stored at link time and never
reads the job dir, so deleting the clip cannot poison it, while deleting
the row would silently drop an outcome (E17-F06). The Loop screen
already draws a linked clip whose file is gone (`clip_thumb` answers
None and the row renders without a picture). `match_rejections` stay
too: inert once the clips are gone, and the only thing that could bring
them back into play is the same job id restored from a backup — when the
user's "not this" decisions are exactly what they would want kept.

The id arrives from the webview. It is one path component under jobs/
or it is refused: no separators, no `..`, nothing absolute, and the
resolved path must sit directly inside jobs/ (a symlink pointing out is
refused with it). A delete verb is the last place to trust a string.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import stat
from pathlib import Path

from .. import config
from . import queue

TERMINAL = ("done", "failed", "cancelled")
_REFUSALS = {
    "pending": "This job is waiting in the queue — cancel it from the queue instead of deleting it.",
    "running": "This job is running — cancel it first.",
}
NOT_A_JOB_ID = "That is not a job id."


def safe_id(job_id: str) -> str | None:
    """`job_id` when it names one entry directly under jobs/, else None."""
    text = str(job_id or "")
    if not text or text in (".", "..") or any(ch in text for ch in "/\\\x00"):
        return None
    as_path = Path(text)
    if as_path.is_absolute() or len(as_path.parts) != 1 or as_path.name != text:
        return None
    return text


def job_dir_for(job_id: str) -> Path | None:
    """The dir a delete may touch, or None: a sane id whose resolved path
    is a direct child of jobs/ — never a path that escapes it."""
    safe = safe_id(job_id)
    if safe is None:
        return None
    root = config.jobs_dir()
    candidate = root / safe
    try:
        if candidate.resolve().parent != root.resolve():
            return None
    except (OSError, RuntimeError):
        return None
    return candidate


def measure(job_dir: Path) -> tuple[int, int]:
    """(files, bytes) under `job_dir` as they are on disk right now.
    Symlinks count by their own size and are never followed."""
    files = size = 0
    for root, _dirs, names in os.walk(job_dir):
        for name in names:
            try:
                st = os.lstat(os.path.join(root, name))
            except OSError:
                continue
            files += 1
            size += st.st_size
    return files, size


def clip_count(job_dir: Path) -> int:
    """The entries of render.json's outputs — what the Review lists. 0
    for a job that never rendered or whose checkpoint cannot be read."""
    try:
        envelope = json.loads((job_dir / "render.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return 0
    data = envelope.get("data") if isinstance(envelope, dict) else None
    outputs = data.get("outputs") if isinstance(data, dict) else None
    return sum(1 for entry in (outputs or []) if isinstance(entry, dict))


def linked_reels(job_id: str) -> int:
    """How many of the job's clips are linked to posted Reels. 0 when the
    loop has never run: its table does not exist until it does."""
    with queue._connect() as conn:  # noqa: SLF001 - same package, one reader
        try:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM published_clips WHERE job_id = ?", (job_id,)
            ).fetchone()
        except sqlite3.OperationalError:
            return 0
    return int(row["n"]) if row else 0


def info(job_id: str) -> dict:
    """What deleting `job_id` would do, and whether it may be done:
    {deletable, reason?, status, exists, clips, bytes, linked_reels}.
    `status` is the row's, None for a dir with no row."""
    base = {"status": None, "exists": False, "clips": 0, "bytes": 0, "linked_reels": 0}
    job_dir = job_dir_for(job_id)
    if job_dir is None:
        return {**base, "deletable": False, "reason": NOT_A_JOB_ID}
    job = queue.get_job(job_id)
    exists = job_dir.is_dir()
    if job_dir.exists() and not exists:
        return {**base, "deletable": False, "reason": "That is not a job folder."}
    verdict = {
        "status": job.status if job else None,
        "exists": exists,
        "clips": clip_count(job_dir) if exists else 0,
        "bytes": measure(job_dir)[1] if exists else 0,
        "linked_reels": linked_reels(job_id),
    }
    if job is None and not exists:
        return {**verdict, "deletable": False, "reason": "There is no job with this id."}
    if job is not None and job.status not in TERMINAL:
        reason = _REFUSALS.get(job.status, f"This job is {job.status}, not finished.")
        return {**verdict, "deletable": False, "reason": reason}
    return {**verdict, "deletable": True}


def remove_tree(job_dir: Path) -> list[str]:
    """rmtree with every failure collected — what could not be removed,
    and why — instead of raised or swallowed. The caller checks whether
    the dir is gone; this only reports."""
    failures: list[str] = []

    def onexc(func, path, exc):
        if isinstance(exc, PermissionError):
            # A read-only file (a source copied off read-only media) fails
            # unlink on Windows until it is writable: one chmod and one
            # retry is the remedy. A file another process holds open fails
            # the retry the same way, and that is what gets collected.
            try:
                os.chmod(path, stat.S_IWRITE)
                func(path)
                return
            except OSError as err:
                exc = err
        failures.append(f"{Path(path).name}: {exc}")

    shutil.rmtree(job_dir, onexc=onexc)
    return failures


def delete(job_id: str) -> dict:
    """The verb: {ok, freed_bytes, error?}. Re-checks everything itself —
    it never trusts that info() was called first, because the shell may
    have asked minutes ago and the job may have been resumed since."""
    verdict = info(job_id)
    if not verdict["deletable"]:
        return {"ok": False, "freed_bytes": 0, "error": verdict["reason"], "status": verdict["status"]}
    job_dir = job_dir_for(job_id)
    if job_dir is None:  # info() said deletable, so this cannot happen; belt for the type
        return {"ok": False, "freed_bytes": 0, "error": NOT_A_JOB_ID, "status": None}
    before = verdict["bytes"]
    if job_dir.exists():
        failures = remove_tree(job_dir)
        if job_dir.exists():
            left = measure(job_dir)[1]
            first = failures[0] if failures else "a file is still in use"
            return {
                "ok": False,
                "freed_bytes": max(0, before - left),
                "error": (
                    f"The job was only partly removed: {max(1, len(failures))} item(s) could "
                    f"not be deleted ({first}). Close anything that has its files open and "
                    "delete it again."
                ),
                "status": verdict["status"],
            }
    dropped = queue.delete_job_rows(job_id)
    return {"ok": True, "freed_bytes": before, "dropped": dropped}
