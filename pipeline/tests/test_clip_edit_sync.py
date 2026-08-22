"""The editor and the analyzer must agree about a clip.

Before this, a whole-job restyle re-rendered every clip from the job's
settings and ignored `clip_edits.json` entirely: a clip framed, trimmed and
restyled by hand in the editor came back from a restyle as if none of that
had happened. These tests pin the three halves of the fix — the camera stage
honours per-clip framing, the render stage honours per-clip style and refuses
to overwrite a structurally-edited clip, and both invalidate their cache when
an edit changes.
"""

import json
from pathlib import Path

import pytest

from publikclip_pipeline import config
from publikclip_pipeline.camera import stage as camera_stage
from publikclip_pipeline.render import stage as render_stage


class FakeJob:
    def __init__(self, path):
        self.dir = path


class FakeCtx:
    def __init__(self, job_dir, settings):
        self.job = FakeJob(job_dir)
        self.settings = settings
        self.messages = []

    @property
    def job_dir(self):
        return self.job.dir

    def emit(self, fraction, message, stage=""):
        self.messages.append(message)


@pytest.fixture
def ctx(tmp_path):
    return FakeCtx(tmp_path, config.Settings())


def write_edits(job_dir: Path, edits: dict) -> None:
    (job_dir / "clip_edits.json").write_text(json.dumps(edits), encoding="utf-8")


# ---------------------------------------------------------------------------
# Camera stage: per-clip framing survives a job-level restyle


def test_clip_framing_overrides_the_job_dial():
    settings = config.Settings()
    settings.camera.gameplay_amount = 0.0
    out = camera_stage._settings_for_clip(settings, {"gameplay_amount": 0.82})
    assert out.camera.gameplay_amount == pytest.approx(0.82)
    assert settings.camera.gameplay_amount == 0.0  # original untouched


def test_clip_framing_keeps_the_rest_of_the_settings():
    """The director reads settings.retention for punch-ins. Handing it only a
    CameraSettings was the bug that made editor renders drift."""
    settings = config.Settings()
    settings.retention.punch_in_sensitivity = 0.77
    settings.lufs_target = -11.0
    out = camera_stage._settings_for_clip(settings, {"camera_mode": "pan"})
    assert out.camera.speaker_change == "pan"
    assert out.retention.punch_in_sensitivity == pytest.approx(0.77)
    assert out.lufs_target == pytest.approx(-11.0)


def test_a_clip_without_framing_overrides_reuses_the_job_settings():
    settings = config.Settings()
    assert camera_stage._settings_for_clip(settings, {}) is settings
    assert camera_stage._settings_for_clip(settings, {"caption_preset": "bold"}) is settings


def test_zero_gameplay_amount_is_an_override_not_an_absence():
    """0.0 is falsy and a legitimate choice: this clip stays a tight crop even
    when the job dial is pushed all the way to gameplay."""
    settings = config.Settings()
    settings.camera.gameplay_amount = 0.9
    out = camera_stage._settings_for_clip(settings, {"gameplay_amount": 0.0})
    assert out.camera.gameplay_amount == 0.0


def test_framing_fingerprint_ignores_non_framing_edits(tmp_path):
    write_edits(tmp_path, {"0": {"caption_preset": "bold", "lufs_target": -9.0}})
    assert camera_stage._framing_fingerprint(tmp_path) == {}


def test_framing_fingerprint_notices_a_framing_edit(tmp_path):
    write_edits(tmp_path, {"1": {"gameplay_amount": 0.5, "caption_preset": "bold"}})
    assert camera_stage._framing_fingerprint(tmp_path) == {"1": {"gameplay_amount": 0.5}}


def test_camera_cache_survives_a_caption_only_edit(tmp_path, ctx):
    traj = tmp_path / "trajectory_00.json"
    traj.write_text("{}")
    data = {
        "trajectories": {"0": str(traj)},
        "camera_settings": ctx.settings.camera.__dict__,
        "retention_settings": ctx.settings.retention.__dict__,
        "clip_framing": {},
    }
    write_edits(tmp_path, {"0": {"caption_preset": "bold"}})
    assert camera_stage.CameraStage().artifacts_ok(ctx, data) is True


def test_camera_cache_is_invalidated_by_a_framing_edit(tmp_path, ctx):
    traj = tmp_path / "trajectory_00.json"
    traj.write_text("{}")
    data = {
        "trajectories": {"0": str(traj)},
        "camera_settings": ctx.settings.camera.__dict__,
        "retention_settings": ctx.settings.retention.__dict__,
        "clip_framing": {},
    }
    write_edits(tmp_path, {"0": {"gameplay_amount": 0.7}})
    assert camera_stage.CameraStage().artifacts_ok(ctx, data) is False


def test_a_job_with_no_edits_file_is_not_forced_to_re_direct(tmp_path, ctx):
    """Jobs directed before this feature have no clip_framing key at all —
    they must not all re-run the expensive camera pass on first resume."""
    traj = tmp_path / "trajectory_00.json"
    traj.write_text("{}")
    data = {
        "trajectories": {"0": str(traj)},
        "camera_settings": ctx.settings.camera.__dict__,
        "retention_settings": ctx.settings.retention.__dict__,
    }
    assert camera_stage.CameraStage().artifacts_ok(ctx, data) is True


# ---------------------------------------------------------------------------
# Render stage: structural edits are never overwritten


def test_changed_bounds_count_as_structural():
    clip = {"start": 10.0, "end": 40.0}
    assert render_stage._has_structural_edits({"start": 12.0, "end": 40.0}, clip) is True
    assert render_stage._has_structural_edits({"start": 10.0, "end": 37.5}, clip) is True


def test_untouched_bounds_are_not_structural():
    clip = {"start": 10.0, "end": 40.0}
    assert render_stage._has_structural_edits({"start": 10.0, "end": 40.0}, clip) is False


def test_dead_space_removal_and_overlays_are_structural():
    clip = {"start": 0.0, "end": 30.0}
    assert render_stage._has_structural_edits(
        {"start": 0.0, "end": 30.0, "remove_dead_space": True}, clip
    ) is True
    assert render_stage._has_structural_edits(
        {"start": 0.0, "end": 30.0, "overlays": [{"id": "a"}]}, clip
    ) is True


def test_style_only_edits_are_not_structural():
    """Style is reproducible here, so those clips are re-rendered (and pick up
    the job's other changes) rather than frozen at their editor version."""
    clip = {"start": 0.0, "end": 30.0}
    edit = {"start": 0.0, "end": 30.0, "caption_preset": "bold", "letterbox_fill": "blur"}
    assert render_stage._has_structural_edits(edit, clip) is False


def test_no_edit_at_all_is_not_structural():
    assert render_stage._has_structural_edits({}, {"start": 0.0, "end": 5.0}) is False


def test_malformed_bounds_do_not_crash_the_render():
    clip = {"start": 0.0, "end": 30.0}
    assert render_stage._has_structural_edits({"start": "oops", "end": None}, clip) is False


# ---------------------------------------------------------------------------
# Render stage: carrying an editor render forward


def test_previous_outputs_are_keyed_by_clip(tmp_path):
    mp4 = tmp_path / "clip_00.mp4"
    mp4.write_bytes(b"x")
    (tmp_path / "render.json").write_text(
        json.dumps({"data": {"outputs": [{"clip": 0, "path": str(mp4)}]}}), encoding="utf-8"
    )
    assert render_stage._previous_outputs(tmp_path)["0"]["path"] == str(mp4)


def test_previous_outputs_skips_files_that_are_gone(tmp_path):
    (tmp_path / "render.json").write_text(
        json.dumps({"data": {"outputs": [{"clip": 0, "path": str(tmp_path / "gone.mp4")}]}}),
        encoding="utf-8",
    )
    assert render_stage._previous_outputs(tmp_path) == {}


def test_previous_outputs_tolerates_a_corrupt_checkpoint(tmp_path):
    (tmp_path / "render.json").write_text("{not json", encoding="utf-8")
    assert render_stage._previous_outputs(tmp_path) == {}


def test_missing_edits_file_reads_as_no_edits(tmp_path):
    assert render_stage._load_clip_edits(tmp_path) == {}


def test_corrupt_edits_file_reads_as_no_edits(tmp_path):
    (tmp_path / "clip_edits.json").write_text("[]", encoding="utf-8")
    assert render_stage._load_clip_edits(tmp_path) == {}


# ---------------------------------------------------------------------------
# Render stage: cache invalidation


def test_render_fingerprint_covers_every_style_the_stage_applies(tmp_path):
    """Each key here is read by run() to override the job's setting. If one is
    applied but not fingerprinted, editing it renders nothing new."""
    write_edits(
        tmp_path,
        {
            "0": {
                "start": 1.0, "end": 9.0, "caption_preset": "bold",
                "caption_overrides": {"font_size": 90}, "lufs_target": -9.0,
                "true_peak_db": -0.5, "letterbox_fill": "blur",
                "remove_dead_space": True, "disabled_cuts": [1],
            }
        },
    )
    fp = render_stage._clip_edits_fingerprint(tmp_path)["0"]
    assert set(fp) == {
        "start", "end", "caption_preset", "caption_overrides", "lufs_target",
        "true_peak_db", "letterbox_fill", "remove_dead_space", "disabled_cuts",
    }


def test_render_fingerprint_ignores_edits_the_render_cannot_see(tmp_path):
    """Opening the editor writes defaults for every field. Titles and
    descriptions are not pixels — they must not force a re-encode."""
    write_edits(tmp_path, {"0": {"title": "hello", "description": "world"}})
    assert render_stage._clip_edits_fingerprint(tmp_path) == {}


def test_render_cache_is_invalidated_by_a_clip_style_edit(tmp_path, ctx):
    mp4 = tmp_path / "clip_00.mp4"
    mp4.write_bytes(b"x")
    data = {
        "outputs": [{"clip": 0, "path": str(mp4)}],
        "caption_preset": ctx.settings.caption_preset,
        "camera_settings": ctx.settings.camera.__dict__,
        "caption_style": render_stage._caption_style_fingerprint(ctx),
        "audio": render_stage._audio_fingerprint(ctx),
        "encoder": render_stage._encoder_fingerprint(ctx),
        "clip_edits": {},
    }
    assert render_stage.RenderStage().artifacts_ok(ctx, data) is True
    write_edits(tmp_path, {"0": {"letterbox_fill": "blur"}})
    assert render_stage.RenderStage().artifacts_ok(ctx, data) is False
