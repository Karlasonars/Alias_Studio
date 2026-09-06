"""E20 — Stories mode: the second chain, stage by stage.

Grows with the chain. This file holds what the story chain needs from the
stages it shares (ingest without an audio track, asr reading a chosen
prior), the new narrate stage against a fake synthesiser (the real model
is never loaded here — §3), the story render's caption document and
fingerprint, and the three places a story job used to break: the editor
context, the disk pre-flight and the hardware profile."""

from __future__ import annotations

import json
import subprocess

import pytest

from publikclip_pipeline import chains, config
from publikclip_pipeline.jobs import queue


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("PUBLIKCLIP_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("HF_HOME", raising=False)
    monkeypatch.delenv("TORCH_HOME", raising=False)
    yield


def _story_settings() -> config.Settings:
    settings = config.Settings()
    settings.mode = "stories"
    return settings


def _noop(stage, fraction, message):
    pass


def _silent_video(path, seconds: float = 2.0):
    """A background with NO audio stream — silent b-roll, the normal story
    background — built like test_render_smoke's source (§3)."""
    from publikclip_pipeline.render import ffmpeg_bin

    subprocess.run(
        [
            ffmpeg_bin.ffmpeg(), "-v", "error", "-y",
            "-f", "lavfi", "-i", f"testsrc2=size=640x360:rate=25:duration={seconds}",
            "-an", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(path),
        ],
        check=True, timeout=300,
    )
    return path


# ---------------------------------------------------------------------------
# The three defects a story job hit the moment it existed


def test_context_for_clip_declines_a_story_job_instead_of_raising(tmp_path):
    """The editor's context read diarize, events and score unguarded, so a
    story job (which has none) crashed it with a traceback. It declines
    now — a value the editor renders as its error line — and never
    raises (§5.9)."""
    from publikclip_pipeline.edits import render_clip as rc

    job = queue.create_job("file", "C:/bg.mp4", json.dumps(_story_settings().to_json()))
    # no checkpoints at all: exactly what a story job dir looks like to this reader
    answer = rc.context_for_clip(job.dir, 0)
    assert answer["ok"] is False
    assert answer["code"] == "story-not-editable"
    assert "story" in answer["error"]

    # and a clips job still takes the old path (it fails on the missing
    # checkpoint, as it always did — the decline is for story jobs only)
    clips_job = queue.create_job("file", "C:/x.mp4", json.dumps(config.Settings().to_json()))
    with pytest.raises(FileNotFoundError):
        rc.context_for_clip(clips_job.dir, 0)


def test_a_story_job_is_not_charged_for_models_its_chain_never_loads():
    """The pre-flight used to charge every job the clips model set and N
    rendered clips: a story on a fresh machine could be disk-blocked for
    the speaker, event and face models the chain never fetches."""
    from publikclip_pipeline.jobs import disk

    job = queue.create_job("file", "C:/nowhere/bg.mp4", json.dumps(_story_settings().to_json()))
    needs, unknown = disk.gather(job, _story_settings())
    labels = {n.label for n in needs}
    assert not any("Speaker embeddings" in label for label in labels), labels
    assert not any("Audio events" in label for label in labels), labels
    assert not any("Face & active-speaker" in label for label in labels), labels
    assert "rendered clips" not in labels
    assert "analysis audio" not in labels
    # what the chain DOES load is still charged
    assert any("Speech recognition" in label for label in labels), labels
    # and the story video is named as unsized, never invented (§5.9)
    assert any("story video" in u for u in unknown), unknown

    clips_job = queue.create_job("file", "C:/nowhere/x.mp4", json.dumps(config.Settings().to_json()))
    needs, _ = disk.gather(clips_job, config.Settings())
    labels = {n.label for n in needs}
    assert any("Speaker embeddings" in label for label in labels)
    assert "rendered clips" in labels


def test_a_story_job_is_not_folded_into_the_hardware_profile():
    """Every profile ratio is normalised by the SOURCE duration; a story's
    stages scale with its narration. Folding one in would quietly bend the
    clips estimate, so story jobs are not profiled (§5.9: an honest absence)."""
    from publikclip_pipeline import hardware_profile

    job = queue.create_job("file", "C:/bg.mp4", json.dumps(_story_settings().to_json()))
    queue.write_checkpoint(job, "ingest", 1, {"probe": {"duration_sec": 30.0}})
    with queue._connect() as conn:  # a stage row inside this run, as a real job leaves one
        conn.execute(
            "UPDATE stage_runs SET started_at = 1000.0, finished_at = 1010.0"
            " WHERE job_id = ? AND stage = 'ingest'",
            (job.id,),
        )
    assert hardware_profile.update_after_job(job.id, run_started=1000.0) is None
    assert not hardware_profile.profile_path().exists()


# ---------------------------------------------------------------------------
# ingest: a background with no audio track (F03)


def test_ingest_accepts_a_silent_background_and_its_fingerprint_still_answers(tmp_path):
    from publikclip_pipeline.ingest.stage import IngestStage

    src = _silent_video(tmp_path / "bg.mp4")
    job = queue.create_job("file", str(src), json.dumps(_story_settings().to_json()))
    ctx = queue.StageContext(job=job, settings=_story_settings(), progress=_noop)

    stage = IngestStage(needs_audio=False)
    data = stage.run(ctx)
    assert data["audio_path"] is None
    assert data["probe"]["has_audio"] is False
    assert not (job.dir / "audio16k.wav").exists()
    # a checkpoint without a wav is not stale for lacking one
    assert stage.artifacts_ok(ctx, data) is True
    # a moved background is still caught: the media check stands
    assert stage.artifacts_ok(ctx, {**data, "media_path": str(tmp_path / "gone.mp4")}) is False

    # the clips chain keeps refusing it, word for word
    with pytest.raises(queue.StageError) as err:
        IngestStage().run(ctx)
    assert err.value.code == "no-audio-track"


def test_the_clips_chain_builds_ingest_with_audio_required():
    from publikclip_pipeline import cli

    ingest = cli._stages("clips")[0]
    assert ingest.name == "ingest" and ingest.needs_audio is True
    assert chains.chain_for("clips")[0] == "ingest"
