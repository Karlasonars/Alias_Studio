"""Queue contract (T-08 / E2-F04).

The queue is the jobs table: rows with status 'pending', FIFO. Everything
the Rust runner does is ask next_pending() (via `jobs next`) and spawn the
answer, so every scheduling decision is pinned here in Python. What is NOT
testable here: the runner loop itself, cancel-holds-queue, the cancel latch
and pause — those are Rust session state and gesture semantics, verified by
the PR's hand-test checklist. The Python half of cancel-holds-queue that IS
pinnable — a cancelled job is never offered again — is below.
"""

import json

import pytest

from publikclip_pipeline import cli, config
from publikclip_pipeline.jobs import queue


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("PUBLIKCLIP_HOME", str(tmp_path / "home"))
    yield


def _job(source: str = "C:/nowhere/video.mp4") -> queue.Job:
    return queue.create_job("file", source, json.dumps(config.Settings().to_json()))


def _write_flag(ctx):
    (ctx.job_dir / queue.CANCEL_FLAG).write_text("1", encoding="utf-8")


class Recorder(queue.Stage):
    schema_version = 1

    def __init__(self, name, on_run=None):
        self.name = name
        self._on_run = on_run

    def run(self, ctx):
        if self._on_run is not None:
            self._on_run(ctx)
        return {}


def test_next_pending_is_fifo_and_only_pending():
    a, b, c = _job("a.mp4"), _job("b.mp4"), _job("c.mp4")
    assert queue.next_pending().id == a.id
    # every non-pending status is ineligible, whatever it is
    queue.set_job_status(a.id, "running")
    assert queue.next_pending().id == b.id
    queue.set_job_status(b.id, "done")
    assert queue.next_pending().id == c.id
    queue.set_job_status(c.id, "failed", "boom")
    assert queue.next_pending() is None


def test_the_queue_survives_a_restart():
    # Nothing about the queue lives in process memory: rows written through
    # one connection are what a fresh process (fresh connection) sees, in
    # the same order.
    a, b = _job("a.mp4"), _job("b.mp4")
    with queue._connect() as conn:
        rows = conn.execute(
            "SELECT id FROM jobs WHERE status = 'pending' ORDER BY created_at ASC, rowid ASC"
        ).fetchall()
    assert [r["id"] for r in rows] == [a.id, b.id]
    assert queue.next_pending().id == a.id


def test_one_failure_does_not_stop_the_rest():
    a, b = _job("a.mp4"), _job("b.mp4")
    queue.set_job_status(a.id, "failed", "stage blew up")
    nxt = queue.next_pending()
    assert nxt is not None and nxt.id == b.id
    # and the failed job stays terminal - no automatic retry, ever
    queue.set_job_status(b.id, "done")
    assert queue.next_pending() is None


def test_reconcile_touches_only_running_rows():
    ghost = _job("ghost.mp4")
    queue.set_job_status(ghost.id, "running")
    ghost_cancelled = _job("ghost-cancelled.mp4")
    queue.set_job_status(ghost_cancelled.id, "running")
    (ghost_cancelled.dir / queue.CANCELLED_MARKER).write_text("1", encoding="utf-8")
    pending = _job("pending.mp4")
    done = _job("done.mp4")
    queue.set_job_status(done.id, "done")
    cancelled = _job("cancelled.mp4")
    queue.set_job_status(cancelled.id, "cancelled")

    out = queue.reconcile_stale_running()

    assert {(o["job_id"], o["status"]) for o in out} == {
        (ghost.id, "failed"),
        (ghost_cancelled.id, "cancelled"),
    }
    g = queue.get_job(ghost.id)
    assert g.status == "failed" and g.error.startswith("interrupted")
    # the marker is disk truth: a hard-killed cancel whose one-shot never ran
    assert queue.get_job(ghost_cancelled.id).status == "cancelled"
    # nothing else moves - especially no resurrection of a cancelled job
    assert queue.get_job(pending.id).status == "pending"
    assert queue.get_job(done.id).status == "done"
    assert queue.get_job(cancelled.id).status == "cancelled"


def test_cancel_pending_guards_on_pending():
    job = _job()
    assert queue.cancel_pending(job.id) == {"marked": True, "status": "cancelled"}
    assert queue.get_job(job.id).status == "cancelled"
    assert (job.dir / queue.CANCELLED_MARKER).exists()
    running = _job("r.mp4")
    queue.set_job_status(running.id, "running")
    assert queue.cancel_pending(running.id) == {"marked": False, "status": "running"}
    assert queue.cancel_pending("no-such-job") == {"marked": False, "status": None}


def test_a_cancelled_job_is_never_offered_again():
    # The Python half of cancel-holds-queue: whatever the shell's latch
    # does, a cancelled job must not come back through next_pending - not
    # after the boundary cancel, not after reconcile.
    a, b = _job("a.mp4"), _job("b.mp4")
    with pytest.raises(queue.JobCancelled):
        queue.run_stages(a, [Recorder("s1", on_run=_write_flag), Recorder("s2")], lambda *_: None)
    assert queue.get_job(a.id).status == "cancelled"
    nxt = queue.next_pending()
    assert nxt is not None and nxt.id == b.id
    queue.reconcile_stale_running()
    assert queue.get_job(a.id).status == "cancelled"
    assert queue.next_pending().id == b.id


def test_jobs_create_enqueues_without_running(capsys):
    rc = cli.main(["jobs", "create", "C:/nowhere/clip.mp4", "--gameplay-amount", "0.0"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    job = queue.get_job(out["job_id"])
    assert job is not None and job.status == "pending"
    # no stage ran, no checkpoint exists - created, not executed
    assert not queue.checkpoint_path(job, "ingest").exists()
    # the flag override reached the snapshot, 0.0 included (5.5)
    snap = json.loads((job.dir / "settings.json").read_text(encoding="utf-8"))
    assert snap["camera"]["gameplay_amount"] == 0.0


def test_jobs_next_verb_answers_the_runner(capsys):
    assert cli.main(["jobs", "next"]) == 0
    assert json.loads(capsys.readouterr().out.strip()) == {"job_id": None}
    job = _job()
    assert cli.main(["jobs", "next"]) == 0
    assert json.loads(capsys.readouterr().out.strip()) == {"job_id": job.id}
