"""Deleting a finished job (T-30 / E2-F01): jobs/delete.py's contract.

Synthetic job dirs under a tmp PUBLIKCLIP_HOME — bytes on disk, never
media, never a model (CLAUDE.md §3). What this file pins: only terminal
jobs go; a delete takes the dir and BOTH row kinds and nothing of any
other job; an already-missing dir is not an error; a dir with no row is
deletable; a partial failure keeps the row and says so; the numbers in
the confirmation are measured off disk; a path-traversal id from the
webview is refused and touches nothing outside jobs/; and the Instagram
links survive, named.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from publikclip_pipeline import cli, config
from publikclip_pipeline.insights import calibration
from publikclip_pipeline.jobs import delete as job_delete
from publikclip_pipeline.jobs import queue


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("PUBLIKCLIP_HOME", str(tmp_path / "home"))
    yield


def _job(status: str = "done", *, clips: int = 2, mode: str = "clips", media_bytes: int = 1000) -> queue.Job:
    """A job dir the way a finished run leaves one: media, an intermediate
    folder, two checkpoints with their stage rows, rendered outputs."""
    settings = config.Settings()
    settings.mode = mode
    job = queue.create_job("file", "C:/nowhere/video.mp4", json.dumps(settings.to_json()))
    (job.dir / "media.mp4").write_bytes(b"m" * media_bytes)
    (job.dir / "t2frames").mkdir()
    (job.dir / "t2frames" / "f0.jpg").write_bytes(b"j" * 10)
    queue.write_checkpoint(job, "ingest", 1, {"probe": {"duration_sec": 30.0}})
    clips_dir = job.dir / "clips"
    clips_dir.mkdir()
    outputs = []
    for i in range(clips):
        path = clips_dir / (f"clip_{i:02d}.mp4" if mode == "clips" else "story.mp4")
        path.write_bytes(b"c" * (100 + i))
        entry = {"clip": i, "path": str(path), "duration": 12.0}
        if mode == "stories":
            entry["story"] = True
        outputs.append(entry)
    queue.write_checkpoint(job, "render", 1, {"outputs": outputs})
    queue.set_job_status(job.id, status)
    refreshed = queue.get_job(job.id)
    assert refreshed is not None
    return refreshed


def _disk_bytes(root: Path) -> int:
    return sum(p.stat().st_size for p in root.rglob("*") if p.is_file())


def _rows(job_id: str) -> tuple[bool, int]:
    return queue.get_job(job_id) is not None, len(queue.stage_statuses(job_id))


# ---------------------------------------------------------------------------
# Who may go


def test_only_terminal_jobs_are_deletable_and_delete_rechecks_on_its_own():
    """pending has cancel-pending, running has T-07: neither is this
    verb's to touch, and `delete` refuses them itself — it never trusts
    that delete-info was asked, let alone answered 'deletable'."""
    for status in ("pending", "running"):
        job = _job(status)
        verdict = job_delete.info(job.id)
        assert verdict["deletable"] is False and verdict["status"] == status
        assert verdict["reason"]
        result = job_delete.delete(job.id)  # straight to the verb, no info() first
        assert result["ok"] is False and result["error"] == verdict["reason"]
        assert job.dir.is_dir() and _rows(job.id) == (True, 2)
    for status in ("done", "failed", "cancelled"):
        job = _job(status)
        assert job_delete.info(job.id)["deletable"] is True
        result = job_delete.delete(job.id)
        assert result["ok"] is True and "error" not in result
        assert not job.dir.exists() and _rows(job.id) == (False, 0)


def test_delete_removes_the_dir_and_both_row_kinds_and_leaves_other_jobs_alone():
    victim, bystander = _job("done"), _job("failed")
    bystander_bytes = _disk_bytes(bystander.dir)
    result = job_delete.delete(victim.id)
    assert result["ok"] is True
    assert result["dropped"] == {"jobs": 1, "stage_runs": 2}
    assert not victim.dir.exists()
    assert _rows(victim.id) == (False, 0)
    # the other job: dir byte-for-byte, row, stage rows
    assert bystander.dir.is_dir() and _disk_bytes(bystander.dir) == bystander_bytes
    assert _rows(bystander.id) == (True, 2)
    assert [j.id for j in queue.list_jobs()] == [bystander.id]


def test_an_already_missing_dir_is_not_an_error_the_rows_still_go():
    """A folder removed by hand in Explorer leaves a row the rail cannot
    show: deleting it is bookkeeping, and it succeeds."""
    job = _job("done")
    shutil.rmtree(job.dir)
    verdict = job_delete.info(job.id)
    assert verdict["deletable"] is True and verdict["exists"] is False
    assert verdict["clips"] == 0 and verdict["bytes"] == 0
    result = job_delete.delete(job.id)
    assert result["ok"] is True and result["freed_bytes"] == 0
    assert _rows(job.id) == (False, 0)


def test_a_dir_with_no_row_is_deletable_and_removed():
    """db.sqlite3 replaced under an existing jobs/ folder, or a folder
    copied in by hand: the rail lists it, the queue does not, and nothing
    can be running it — terminal by definition."""
    orphan = config.jobs_dir() / "20260101-000000-abcdef"
    orphan.mkdir(parents=True)
    (orphan / "media.mp4").write_bytes(b"x" * 500)
    (orphan / "clips").mkdir()
    (orphan / "clips" / "clip_00.mp4").write_bytes(b"y" * 50)
    verdict = job_delete.info(orphan.name)
    assert verdict["deletable"] is True and verdict["status"] is None
    assert verdict["bytes"] == 550 and verdict["clips"] == 0  # no render.json: nothing the Review would list
    result = job_delete.delete(orphan.name)
    assert result["ok"] is True and result["freed_bytes"] == 550
    assert result["dropped"] == {"jobs": 0, "stage_runs": 0}
    assert not orphan.exists()
    # nothing at all: neither dir nor row
    verdict = job_delete.info("20260101-000000-000000")
    assert verdict["deletable"] is False and "no job" in verdict["reason"]
    assert job_delete.delete("20260101-000000-000000")["ok"] is False


def test_a_partial_failure_keeps_the_row_and_names_it(monkeypatch):
    """Windows: a clip held open by the Review player or an Explorer
    preview cannot be unlinked. Simulated by the remover, not by a real
    lock: the one file refuses, the row stays, the answer says 'partly',
    and once the file is free a second delete finishes the job."""
    job = _job("done", clips=2)
    before = _disk_bytes(job.dir)
    locked = job.dir / "clips" / "clip_01.mp4"
    real_unlink = os.unlink

    def unlink(path, *args, **kwargs):
        if Path(path).name == locked.name:
            raise PermissionError(32, "The process cannot access the file because it is being used")
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(os, "unlink", unlink)
    result = job_delete.delete(job.id)
    assert result["ok"] is False
    assert "only partly removed" in result["error"] and "clip_01.mp4" in result["error"]
    assert result["freed_bytes"] == before - _disk_bytes(job.dir) > 0   # what actually went, measured
    assert locked.exists() and job.dir.is_dir()
    assert _rows(job.id) == (True, 2)            # the row is intact: the rail and the queue still show it
    assert queue.get_job(job.id).status == "done"
    # info still answers, with what is left
    verdict = job_delete.info(job.id)
    assert verdict["deletable"] is True and verdict["bytes"] == _disk_bytes(job.dir)

    monkeypatch.setattr(os, "unlink", real_unlink)
    result = job_delete.delete(job.id)
    assert result["ok"] is True
    assert not job.dir.exists() and _rows(job.id) == (False, 0)


def test_a_read_only_file_is_made_writable_and_removed():
    """Not a partial failure: a source copied off read-only media is the
    user's to delete, and one chmod is the remedy."""
    job = _job("done")
    import stat

    os.chmod(job.dir / "media.mp4", stat.S_IREAD)
    result = job_delete.delete(job.id)
    assert result["ok"] is True and not job.dir.exists()


# ---------------------------------------------------------------------------
# The numbers in the confirmation


def test_info_measures_bytes_off_disk_and_counts_the_outputs_the_review_lists():
    clips_job = _job("done", clips=3, media_bytes=4321)
    verdict = job_delete.info(clips_job.id)
    assert verdict["bytes"] == _disk_bytes(clips_job.dir)
    assert verdict["bytes"] >= 4321 + 10 + 100 + 101 + 102     # media, frame, three clips — and the checkpoints
    assert verdict["clips"] == 3
    # a story job has one output in render.json (D-20): one, not zero, not "clips"
    story_job = _job("done", clips=1, mode="stories")
    verdict = job_delete.info(story_job.id)
    assert verdict["clips"] == 1 and verdict["bytes"] == _disk_bytes(story_job.dir)
    # a job that failed before rendering: no outputs to name, the bytes still real
    failed = _job("failed", clips=0)
    (failed.dir / "render.json").unlink()
    verdict = job_delete.info(failed.id)
    assert verdict["clips"] == 0 and verdict["bytes"] == _disk_bytes(failed.dir) > 0
    # an unreadable checkpoint is zero clips, not a crash
    (failed.dir / "render.json").write_bytes(b"\xff\xfe not json")
    assert job_delete.info(failed.id)["clips"] == 0


def test_linked_reels_are_named_and_the_calibration_rows_survive():
    """E17-F06: the outcome history is not the job's to take with it. The
    link row stays, the fit's inputs stay, and the Loop screen renders
    the linked clip without its picture rather than crashing."""
    job = _job("done", clips=2)
    other = _job("done", clips=1)
    calibration.link_clip(job.id, 1, "reel-1", {"score": 0.7, "summary": "the chair", "start": 0.0, "end": 12.0})
    calibration.link_clip(other.id, 0, "reel-2", {"score": 0.4, "summary": "other"})
    assert job_delete.info(job.id)["linked_reels"] == 1
    assert job_delete.info(other.id)["linked_reels"] == 1
    assert job_delete.delete(job.id)["ok"] is True
    kept = {r["ig_media_id"]: r for r in calibration.tracked()}
    assert set(kept) == {"reel-1", "reel-2"} and kept["reel-1"]["job_id"] == job.id
    overview = calibration.overview()
    gone = next(r for r in overview["linked"] if r["media_id"] == "reel-1")
    assert gone["clip_thumb"] is None and gone["summary"] == "the chair" and gone["clip_duration"] == 12.0
    assert all(c["job_id"] != job.id for c in overview["clip_library"])
    # a job the loop never touched: 0, also when the loop's table does not exist yet
    assert job_delete.info(other.id)["linked_reels"] == 1


def test_linked_reels_is_zero_before_the_loop_has_ever_run():
    job = _job("done")
    with queue._connect() as conn:  # noqa: SLF001 - proving the table is absent
        conn.execute("DROP TABLE IF EXISTS published_clips")
    assert job_delete.info(job.id)["linked_reels"] == 0
    assert job_delete.delete(job.id)["ok"] is True


# ---------------------------------------------------------------------------
# The id comes from the webview


def test_a_traversal_id_is_refused_and_deletes_nothing_outside_jobs(tmp_path):
    home = config.ensure_home()
    victim_dir = config.models_dir()
    victim = victim_dir / "weights.bin"
    victim.write_bytes(b"w" * 64)
    (home / "settings.json").write_text("{}", encoding="utf-8")
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (outside / "keep.txt").write_bytes(b"k")
    bad_ids = [
        "..\\models", "../models", "..", ".", "", "jobs", "x/y", "x\\y",
        str(victim_dir), str(outside), str(home), "\\models", "/models",
        "C:models", "..\\..\\elsewhere", "20260101-000000-abcdef/..", "a\x00b",
    ]
    for bad in bad_ids:
        verdict = job_delete.info(bad)
        assert verdict["deletable"] is False, bad
        assert verdict["reason"] == job_delete.NOT_A_JOB_ID or "no job" in verdict["reason"], bad
        result = job_delete.delete(bad)
        assert result["ok"] is False, bad
        assert job_delete.job_dir_for(bad) is None or job_delete.job_dir_for(bad).parent == config.jobs_dir(), bad
    assert victim.read_bytes() == b"w" * 64 and victim_dir.is_dir()
    assert (home / "settings.json").exists() and (outside / "keep.txt").exists()
    assert config.jobs_dir().is_dir()
    # a symlink inside jobs/ that points outside is refused with the rest
    link = config.jobs_dir() / "20260101-000000-1inked"
    try:
        os.symlink(outside, link, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("no symlink privilege here")
    assert job_delete.job_dir_for(link.name) is None
    assert job_delete.delete(link.name)["ok"] is False
    assert (outside / "keep.txt").exists() and link.exists()


def test_a_plain_file_under_jobs_is_not_a_job():
    stray = config.jobs_dir() / "notes.txt"
    stray.parent.mkdir(parents=True, exist_ok=True)
    stray.write_text("x", encoding="utf-8")
    verdict = job_delete.info("notes.txt")
    assert verdict["deletable"] is False and "not a job folder" in verdict["reason"]
    assert job_delete.delete("notes.txt")["ok"] is False and stray.exists()


# ---------------------------------------------------------------------------
# The verbs, as the shell calls them


def _last_json(capsys) -> dict:
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def test_the_verbs_print_one_json_line_and_exit_by_outcome(capsys):
    job = _job("done", clips=2)
    assert cli.main(["jobs", "delete-info", job.id]) == 0
    verdict = _last_json(capsys)
    assert verdict["deletable"] is True and verdict["clips"] == 2 and verdict["bytes"] > 0
    assert set(verdict) >= {"deletable", "status", "exists", "clips", "bytes", "linked_reels"}
    assert cli.main(["jobs", "delete", job.id]) == 0
    result = _last_json(capsys)
    assert result["ok"] is True and result["freed_bytes"] == verdict["bytes"]
    assert not job.dir.exists()
    # gone: the verb says so and exits non-zero for a CLI caller
    assert cli.main(["jobs", "delete", job.id]) == 1
    result = _last_json(capsys)
    assert result["ok"] is False and result["freed_bytes"] == 0 and result["error"]
    pending = _job("pending")
    assert cli.main(["jobs", "delete-info", pending.id]) == 0
    assert _last_json(capsys)["deletable"] is False
    assert cli.main(["jobs", "delete", pending.id]) == 1
    assert pending.dir.is_dir()
