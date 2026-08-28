"""T-14 / E14-F02: resume from a chosen stage.

The mechanism is deliberately one checkpoint deletion plus the cascade §4
rule 2 already provides — these tests prove the choice re-runs the chosen
stage and everything after and NOTHING before (run-counts, not vibes), that
invalidating render preserves what adoption preserves (T-07's
delete-the-file answer, reused), and that resume_info offers a failed
job's stage as the default, no default for a finished job, and measured
estimates only where every stage in the tail has a sample (§5.9)."""

import json
import statistics

import pytest

from publikclip_pipeline import config, hardware_profile
from publikclip_pipeline.jobs import queue
from publikclip_pipeline.render import stage as render_stage


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("PUBLIKCLIP_HOME", str(tmp_path / "home"))
    yield


def _settings_json() -> str:
    return json.dumps(config.Settings().to_json())


class Counting(queue.Stage):
    schema_version = 1

    def __init__(self, name):
        self.name = name
        self.runs = 0

    def run(self, ctx):
        self.runs += 1
        return {"runs": self.runs}


def test_choosing_a_stage_reruns_it_and_everything_after_and_nothing_before():
    job = queue.create_job("file", "C:/x.mp4", _settings_json())
    stages = [Counting("alpha"), Counting("beta"), Counting("gamma")]
    queue.run_stages(job, stages, lambda *a: None)
    assert [s.runs for s in stages] == [1, 1, 1]

    queue.invalidate_stage(job, "beta")
    queue.run_stages(job, stages, lambda *a: None)
    # alpha served from its checkpoint; beta re-ran by the deletion; gamma
    # re-ran by the cascade — no second cascade was built for this.
    assert [s.runs for s in stages] == [1, 2, 2]


def _seed_render_job(job, structural_clip=1):
    clips_dir = job.dir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    for i in range(3):
        path = clips_dir / f"clip_{i:02d}.mp4"
        path.write_bytes(b"mp4")
        outputs.append({"clip": i, "path": str(path), "duration": 30.0})
    queue.write_checkpoint(job, "render", 1, {"outputs": outputs, "kept_from_editor": []})
    (job.dir / "score.json").write_text(
        json.dumps({"schema_version": 1, "data": {"clips": [
            {"start": i * 40.0, "end": i * 40.0 + 30.0} for i in range(3)
        ]}}),
        encoding="utf-8",
    )
    # Clip `structural_clip` was reshaped in the editor AFTER that render —
    # so it is not in kept_from_editor, and only current clip_edits can
    # know it must be preserved.
    (job.dir / "clip_edits.json").write_text(
        json.dumps({str(structural_clip): {"remove_dead_space": [[1.0, 2.0]]}}),
        encoding="utf-8",
    )
    return outputs


def test_invalidating_render_deletes_files_never_the_adoption_map():
    job = queue.create_job("file", "C:/x.mp4", _settings_json())
    outputs = _seed_render_job(job, structural_clip=1)

    result = queue.invalidate_stage(job, "render")
    assert result["dropped_clips"] == [0, 2]
    # The reproducible clips' files are gone — artifacts_ok's exists()
    # check routes the re-run, T-07's exact mechanism.
    assert not (job.dir / "clips" / "clip_00.mp4").exists()
    assert not (job.dir / "clips" / "clip_02.mp4").exists()
    # The structurally-edited clip keeps its file AND the checkpoint that
    # is its adoption map survives: without render.json, run() would
    # re-render that clip from job settings and destroy the user's cuts.
    assert (job.dir / "clips" / "clip_01.mp4").exists()
    assert queue.checkpoint_path(job, "render").exists()
    adopted = render_stage._previous_outputs(job.dir)
    assert "1" in adopted and adopted["1"]["path"] == outputs[1]["path"]


def test_render_invalidation_is_an_honest_noop_when_every_clip_is_protected():
    job = queue.create_job("file", "C:/x.mp4", _settings_json())
    _seed_render_job(job)
    (job.dir / "clip_edits.json").write_text(
        json.dumps({str(i): {"remove_dead_space": [[1.0, 2.0]]} for i in range(3)}),
        encoding="utf-8",
    )
    result = queue.invalidate_stage(job, "render")
    assert result["dropped_clips"] == []
    for i in range(3):
        assert (job.dir / "clips" / f"clip_{i:02d}.mp4").exists()


# ---------------------------------------------------------------------------
# resume_info: statuses, the default, and measured-or-silent estimates


def _write_ingest(job, duration=600.0):
    queue.write_checkpoint(job, "ingest", 1, {"probe": {"duration_sec": duration}})


def _write_profile(samples_by_stage):
    profile = {
        "key": "test-key",
        "measured": {
            "test-key": {
                "stages": {
                    name: {"samples": samples}
                    for name, samples in samples_by_stage.items()
                },
                "jobs": 3,
            }
        },
    }
    hardware_profile.profile_path().parent.mkdir(parents=True, exist_ok=True)
    hardware_profile.profile_path().write_text(json.dumps(profile), encoding="utf-8")


def test_a_failed_job_offers_its_failed_stage_a_finished_job_offers_none():
    job = queue.create_job("file", "C:/x.mp4", _settings_json())
    queue.set_job_status(job.id, "failed", "score: boom")
    (job.dir / queue.ERROR_FILE).write_text(
        json.dumps({"code": "unknown", "cause": "x", "stage": "score"}), encoding="utf-8"
    )
    info = queue.resume_info(queue.get_job(job.id))
    assert info["default_stage"] == "score"
    by_name = {s["name"]: s for s in info["stages"]}
    assert by_name["score"]["status"] == "failed"

    done = queue.create_job("file", "C:/y.mp4", _settings_json())
    queue.set_job_status(done.id, "done")
    _write_ingest(done)
    info = queue.resume_info(queue.get_job(done.id))
    # a job that finished must not pretend a failure happened
    assert info["default_stage"] is None
    assert {s["name"]: s["status"] for s in info["stages"]}["ingest"] == "done"


def test_estimates_are_measured_medians_or_silent_never_partial(monkeypatch):
    job = queue.create_job("file", "C:/x.mp4", _settings_json())
    _write_ingest(job, duration=600.0)
    full = {name: [0.01 * (i + 1), 0.02 * (i + 1)] for i, name in enumerate(hardware_profile.STAGES)}
    _write_profile(full)
    info = queue.resume_info(queue.get_job(job.id))
    by_name = {s["name"]: s for s in info["stages"]}
    # from camera = median(camera) + median(render), scaled by duration
    names = list(hardware_profile.STAGES)
    expected = 600.0 * sum(statistics.median(full[n]) for n in names[names.index("camera"):])
    assert by_name["camera"]["estimate_sec"] == int(round(expected))

    # One stage without a sample under this key: every estimate whose tail
    # includes it goes silent — a partial sum is a fabricated number with
    # extra steps (§5.9). Stages after it still estimate.
    del full["camera"]
    _write_profile(full)
    info = queue.resume_info(queue.get_job(job.id))
    by_name = {s["name"]: s for s in info["stages"]}
    assert by_name["ingest"]["estimate_sec"] is None
    assert by_name["camera"]["estimate_sec"] is None
    assert by_name["render"]["estimate_sec"] is not None


def test_no_ingest_probe_means_no_estimate_at_all():
    job = queue.create_job("file", "C:/x.mp4", _settings_json())
    _write_profile({name: [0.1] for name in hardware_profile.STAGES})
    info = queue.resume_info(queue.get_job(job.id))
    assert info["duration_sec"] is None
    assert all(s["estimate_sec"] is None for s in info["stages"])


def test_stage_order_stays_in_sync_with_the_real_pipeline():
    # hardware_profile.STAGES is the light-import copy the picker and the
    # --from-stage choices use; cli._stages() is the truth. Drift here
    # would let the picker offer a stage the pipeline does not run.
    from publikclip_pipeline import cli

    assert tuple(s.name for s in cli._stages()) == hardware_profile.STAGES
