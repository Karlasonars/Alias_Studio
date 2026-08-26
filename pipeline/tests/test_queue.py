"""Job queue + checkpoint/resume contract tests.

The resume guarantee is the whole point of M0: kill anywhere, re-run, and
only missing/stale work repeats. These tests exercise that contract without
any media."""

import json

import pytest

from publikclip_pipeline import config
from publikclip_pipeline.jobs import queue


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("PUBLIKCLIP_HOME", str(tmp_path / "home"))
    yield


def _settings_json() -> str:
    return json.dumps(config.Settings().to_json())


class CountingStage(queue.Stage):
    name = "counting"
    schema_version = 1

    def __init__(self):
        self.runs = 0

    def run(self, ctx):
        self.runs += 1
        return {"runs": self.runs}


class FailingStage(queue.Stage):
    name = "failing"
    schema_version = 1

    def run(self, ctx):
        raise queue.StageError("boom, but politely")


class ArtifactStage(queue.Stage):
    name = "artifact"
    schema_version = 1

    def __init__(self):
        self.runs = 0

    def run(self, ctx):
        self.runs += 1
        out = ctx.job_dir / "artifact.bin"
        out.write_bytes(b"data")
        return {"path": str(out)}

    def artifacts_ok(self, ctx, data):
        from pathlib import Path

        return Path(data["path"]).exists()


def _noop_progress(stage, fraction, message):
    pass


def test_create_and_get_job():
    job = queue.create_job("file", "/tmp/x.mp4", _settings_json())
    fetched = queue.get_job(job.id)
    assert fetched is not None
    assert fetched.source == "/tmp/x.mp4"
    assert job.dir.exists()
    assert (job.dir / "settings.json").exists()


def test_stage_runs_once_then_caches():
    job = queue.create_job("file", "/tmp/x.mp4", _settings_json())
    stage = CountingStage()
    queue.run_stages(job, [stage], _noop_progress)
    queue.run_stages(job, [stage], _noop_progress)
    assert stage.runs == 1  # second run served from checkpoint


def test_schema_version_bump_invalidates():
    job = queue.create_job("file", "/tmp/x.mp4", _settings_json())
    stage = CountingStage()
    queue.run_stages(job, [stage], _noop_progress)
    stage.schema_version = 2
    queue.run_stages(job, [stage], _noop_progress)
    assert stage.runs == 2


def test_missing_artifact_invalidates_checkpoint():
    job = queue.create_job("file", "/tmp/x.mp4", _settings_json())
    stage = ArtifactStage()
    queue.run_stages(job, [stage], _noop_progress)
    (job.dir / "artifact.bin").unlink()
    queue.run_stages(job, [stage], _noop_progress)
    assert stage.runs == 2


def test_corrupt_checkpoint_reruns():
    job = queue.create_job("file", "/tmp/x.mp4", _settings_json())
    stage = CountingStage()
    queue.run_stages(job, [stage], _noop_progress)
    queue.checkpoint_path(job, stage.name).write_text("{not json")
    queue.run_stages(job, [stage], _noop_progress)
    assert stage.runs == 2


def test_stage_error_marks_job_failed():
    job = queue.create_job("file", "/tmp/x.mp4", _settings_json())
    with pytest.raises(queue.StageError):
        queue.run_stages(job, [FailingStage()], _noop_progress)
    fetched = queue.get_job(job.id)
    assert fetched.status == "failed"
    assert "politely" in (fetched.error or "")


def test_failure_then_resume_skips_completed_stages():
    job = queue.create_job("file", "/tmp/x.mp4", _settings_json())
    counting = CountingStage()
    with pytest.raises(queue.StageError):
        queue.run_stages(job, [counting, FailingStage()], _noop_progress)
    assert counting.runs == 1

    class FixedStage(queue.Stage):
        name = "failing"  # same name — simulates the bug being fixed
        schema_version = 1

        def run(self, ctx):
            return {"ok": True}

    results = queue.run_stages(job, [counting, FixedStage()], _noop_progress)
    assert counting.runs == 1  # not re-run
    assert results["failing"] == {"ok": True}
    assert queue.get_job(job.id).status == "done"


def test_a_rerun_stage_invalidates_every_stage_after_it():
    """Rule 2 of the checkpoint contract, which nothing exercised directly.
    The chain is linear, so a stage that re-runs must force everything
    downstream to re-run too — otherwise a recomputed upstream feeds a
    downstream that is still serving output derived from the old one."""

    class AlwaysStale(queue.Stage):
        name = "upstream"
        schema_version = 1

        def __init__(self):
            self.runs = 0

        def run(self, ctx):
            self.runs += 1
            return {"runs": self.runs}

        def artifacts_ok(self, ctx, data):
            return False  # something the user changed invalidates this

    job = queue.create_job("file", "/tmp/x.mp4", _settings_json())
    upstream, downstream = AlwaysStale(), CountingStage()
    queue.run_stages(job, [upstream, downstream], _noop_progress)
    assert (upstream.runs, downstream.runs) == (1, 1)

    # downstream's own checkpoint is perfectly fresh and its artifacts_ok
    # would say so — the cascade is what must override that.
    queue.run_stages(job, [upstream, downstream], _noop_progress)
    assert (upstream.runs, downstream.runs) == (2, 2)


# ---------------------------------------------------------------------------
# events: the settings fingerprint (T-21)


def _events_ctx(job_dir, settings):
    """Enough of a StageContext for artifacts_ok, plus the curves.json the
    stage writes — so these tests isolate the fingerprint, not file presence."""
    (job_dir / "curves.json").write_text("{}", encoding="utf-8")

    class _Job:
        dir = job_dir

    class _Ctx:
        job = _Job()

        def __init__(self, s):
            self.settings = s

        @property
        def job_dir(self):
            return job_dir

    return _Ctx(settings)


def _events_data(laughter: bool | None):
    """A checkpoint. `None` means one written before the key existed."""
    data = {"timeline": [], "curves_path": "curves.json"}
    if laughter is not None:
        data["settings_used"] = {"laughter_specialist": laughter}
    return data


@pytest.mark.parametrize(
    "stored,current,expected",
    [
        (False, False, True),    # untouched — stays cached
        (True, True, True),      # on, still on — stays cached
        (False, True, False),    # the bug this fixes: turning it ON must re-run
        (True, False, False),    # turning it OFF must re-run too
        (None, False, True),     # pre-fingerprint checkpoint, setting at factory
        (None, True, False),     # pre-fingerprint checkpoint, setting changed
    ],
)
def test_events_fingerprint_tracks_the_laughter_specialist(
    tmp_path, stored, current, expected
):
    """`laughter_specialist` adds a second laughter detector whose spans reach
    the fused timeline, so it changes this stage's output. Before T-21
    artifacts_ok only checked that curves.json existed, and the toggle did
    nothing on any job that had already run.

    The two `None` rows are the ones that make this safe to ship: no events
    checkpoint ever written carries the key, and re-running events cascades
    into candidates, scoring, camera and render."""
    from publikclip_pipeline.events.stage import EventsStage

    settings = config.Settings()
    settings.laughter_specialist = current
    ctx = _events_ctx(tmp_path, settings)
    assert EventsStage().artifacts_ok(ctx, _events_data(stored)) is expected


def test_events_fingerprint_still_requires_curves_json(tmp_path):
    """The artifact check the fingerprint was added alongside, not instead of:
    every downstream stage reads curves.json by path."""
    from publikclip_pipeline.events.stage import EventsStage

    ctx = _events_ctx(tmp_path, config.Settings())
    (tmp_path / "curves.json").unlink()
    assert EventsStage().artifacts_ok(ctx, _events_data(False)) is False


def test_events_fingerprint_ignores_settings_the_stage_does_not_read(tmp_path):
    """Do not widen beyond what the stage reads. A caption preset or a camera
    dial must not re-run 300k forward passes and cascade into four stages."""
    from publikclip_pipeline.events.stage import EventsStage

    settings = config.Settings()
    settings.caption_preset = "beast"
    settings.camera.gameplay_amount = 0.9
    settings.camera.speaker_change = "pan"
    settings.curve.dynamics = 9.0
    settings.curve.events = 0.0
    settings.retention.punch_in_sensitivity = 0.99
    ctx = _events_ctx(tmp_path, settings)
    assert EventsStage().artifacts_ok(ctx, _events_data(False)) is True
