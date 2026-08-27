"""Cancellation contract (T-07 / E2-F07).

Two mechanisms exist. The hard kill lives in the Rust shell and kills a real
process tree, which no unit test here can exercise; what this file pins is
everything the Python side promises: the cooperative boundary in run_stages,
the mark_cancelled bookkeeping the shell's one-shot calls after a kill, and
the one invariant both share — checkpoints survive a cancel, and resume
needs no changes to keep working afterwards.
"""

import json

import pytest

from publikclip_pipeline import config
from publikclip_pipeline.jobs import queue


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("PUBLIKCLIP_HOME", str(tmp_path / "home"))
    yield


def _job() -> queue.Job:
    return queue.create_job("file", "C:/nowhere/video.mp4", json.dumps(config.Settings().to_json()))


def _noop(stage, fraction, message):
    pass


def _write_flag(ctx):
    (ctx.job_dir / queue.CANCEL_FLAG).write_text("1", encoding="utf-8")


class Recorder(queue.Stage):
    schema_version = 1

    def __init__(self, name, on_run=None):
        self.name = name
        self.runs = 0
        self._on_run = on_run

    def run(self, ctx):
        self.runs += 1
        if self._on_run is not None:
            self._on_run(ctx)
        return {"runs": self.runs}


def test_a_flag_written_mid_stage_cancels_at_the_next_boundary():
    job = _job()
    a, b, c = Recorder("a"), Recorder("b", on_run=_write_flag), Recorder("c")
    with pytest.raises(queue.JobCancelled):
        queue.run_stages(job, [a, b, c], _noop)
    assert (a.runs, b.runs, c.runs) == (1, 1, 0)
    # completed work survives; the cancel itself is on the record
    assert queue.checkpoint_path(job, "a").exists()
    assert queue.checkpoint_path(job, "b").exists()
    assert not queue.checkpoint_path(job, "c").exists()
    assert queue.get_job(job.id).status == "cancelled"
    assert (job.dir / queue.CANCELLED_MARKER).exists()
    assert not (job.dir / queue.CANCEL_FLAG).exists()  # consumed, not left behind


def test_resume_after_a_boundary_cancel_reuses_every_checkpoint():
    job = _job()
    with pytest.raises(queue.JobCancelled):
        queue.run_stages(job, [Recorder("a"), Recorder("b", on_run=_write_flag), Recorder("c")], _noop)
    # resume: same call, fresh stage objects, nothing about resume changed
    a2, b2, c2 = Recorder("a"), Recorder("b"), Recorder("c")
    queue.run_stages(job, [a2, b2, c2], _noop)
    assert (a2.runs, b2.runs, c2.runs) == (0, 0, 1)  # cached, cached, ran
    assert queue.get_job(job.id).status == "done"
    assert not (job.dir / queue.CANCELLED_MARKER).exists()  # cleared at start


def test_a_stale_flag_is_cleared_at_start_not_obeyed():
    # A hard-killed run can leave cancel.requested behind (the one-shot is
    # best-effort). The NEXT run must clear it, not cancel itself instantly.
    job = _job()
    (job.dir / queue.CANCEL_FLAG).write_text("1", encoding="utf-8")
    a = Recorder("a")
    queue.run_stages(job, [a], _noop)
    assert a.runs == 1
    assert queue.get_job(job.id).status == "done"


def test_a_cancel_racing_the_last_stage_leaves_the_job_done():
    # The flag arrives during the final stage: there is no boundary left to
    # observe it, the run completes, and the late bookkeeping one-shot must
    # refuse to flip a finished job.
    job = _job()
    queue.run_stages(job, [Recorder("a"), Recorder("z", on_run=_write_flag)], _noop)
    assert queue.get_job(job.id).status == "done"
    assert queue.mark_cancelled(job.id) == {"marked": False, "status": "done"}
    assert queue.get_job(job.id).status == "done"


def test_mark_cancelled_flips_only_a_running_job():
    job = _job()
    queue.set_job_status(job.id, "running")  # what a hard-killed run leaves behind
    assert queue.mark_cancelled(job.id) == {"marked": True, "status": "cancelled"}
    assert queue.get_job(job.id).status == "cancelled"
    assert (job.dir / queue.CANCELLED_MARKER).exists()
    assert queue.mark_cancelled("no-such-job") == {"marked": False, "status": None}


def test_mark_cancelled_drops_only_the_corrupt_render_outputs(monkeypatch):
    # Kill mid-encode under an older, still-valid checkpoint: the truncated
    # file must go (or a settings revert would serve it as done), the intact
    # file and the checkpoint itself must stay — per-file invalidation.
    job = _job()
    good = job.dir / "clip_00.mp4"
    good.write_bytes(b"fine")
    bad = job.dir / "clip_01.mp4"
    bad.write_bytes(b"truncated")
    queue.write_checkpoint(job, "render", 1, {"outputs": [
        {"clip": 0, "path": str(good), "duration": 10.0},
        {"clip": 1, "path": str(bad), "duration": 12.0},
    ]})
    queue.mark_stage(job.id, "render", "running", 1)  # the killed run was re-rendering
    queue.set_job_status(job.id, "running")
    monkeypatch.setattr(
        "publikclip_pipeline.render.renderer.verify_output",
        lambda out_path, expected_duration: {"ok": out_path.name != "clip_01.mp4"},
    )
    assert queue.mark_cancelled(job.id)["marked"] is True
    assert good.exists()
    assert not bad.exists()
    assert queue.checkpoint_path(job, "render").exists()  # the file, never the checkpoint


def test_cleanup_leaves_outputs_alone_when_render_was_not_mid_run(monkeypatch):
    # Killed during asr: the render checkpoint's outputs are from a completed
    # earlier render and must not even be probed, let alone deleted.
    job = _job()
    clip = job.dir / "clip_00.mp4"
    clip.write_bytes(b"fine")
    queue.write_checkpoint(job, "render", 1, {"outputs": [
        {"clip": 0, "path": str(clip), "duration": 10.0},
    ]})
    queue.mark_stage(job.id, "asr", "running", 1)
    queue.set_job_status(job.id, "running")
    monkeypatch.setattr(
        "publikclip_pipeline.render.renderer.verify_output",
        lambda out_path, expected_duration: {"ok": False},  # would delete if consulted
    )
    assert queue.mark_cancelled(job.id)["marked"] is True
    assert clip.exists()
