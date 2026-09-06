"""E20 — Stories mode: the second chain, stage by stage.

Grows with the chain. This file holds what the story chain needs from the
stages it shares (ingest without an audio track, asr reading a chosen
prior), the new narrate stage against a fake synthesiser (the real model
is never loaded here — §3), the story render's caption document and
fingerprint, and the three places a story job used to break: the editor
context, the disk pre-flight and the hardware profile."""

from __future__ import annotations

import dataclasses
import json
import subprocess
import wave
from pathlib import Path

import numpy as np
import pytest

from publikclip_pipeline import chains, config
from publikclip_pipeline.jobs import queue
from publikclip_pipeline.captions import ass as ass_mod
from publikclip_pipeline.captions import story_card
from publikclip_pipeline.narrate import kokoro_tts, limits
from publikclip_pipeline.narrate import stage as narrate_stage
from publikclip_pipeline.narrate import story as story_mod
from publikclip_pipeline.render import renderer
from publikclip_pipeline.render import stage as render_stage
from publikclip_pipeline.render import story as story_render


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


# ---------------------------------------------------------------------------
# The story text (F01) and its limits


STORY = "The chair\r\n\r\nNobody had moved the chair.  \nWe had not touched it for eleven years.\r\n"


def test_story_parse_splits_title_from_body_and_hashes_the_normalised_text():
    a = story_mod.parse(STORY)
    assert a.title == "The chair"
    assert a.body == "Nobody had moved the chair.\nWe had not touched it for eleven years."
    assert a.word_count == 15
    # CRLF, trailing spaces and trailing blank lines are not identity: the
    # same story from Windows and from a .txt must not re-narrate
    b = story_mod.parse("The chair\n\nNobody had moved the chair.\nWe had not touched it for eleven years.")
    assert a.sha256 == b.sha256 and a.text == b.text
    assert story_mod.parse("Only a title").body == ""
    assert story_mod.parse("   \n\n").word_count == 0
    # a text-mode writer on Windows doubles line breaks: still the same story
    assert story_mod.parse(STORY.replace("\n", "\r\n")).sha256 == a.sha256


def test_story_store_and_load_round_trip_lf_utf8(tmp_path):
    path = story_mod.store(tmp_path, STORY)
    raw = path.read_bytes()
    assert b"\r" not in raw and raw.endswith(b"\n")
    assert story_mod.load(tmp_path).sha256 == story_mod.parse(STORY).sha256


def test_limits_refuse_over_max_and_warn_over_warn_naming_the_numbers():
    ok = " ".join(["word"] * limits.WARN_WORDS)
    assert limits.check(ok) is None and limits.warning(ok) is None
    long = " ".join(["word"] * (limits.WARN_WORDS + 1))
    assert limits.check(long) is None
    assert str(limits.WARN_WORDS) in (limits.warning(long) or "")
    too_long = " ".join(["word"] * (limits.MAX_WORDS + 7))
    refusal = limits.check(too_long)
    assert refusal and str(limits.MAX_WORDS) in refusal and "7 words" in refusal
    assert "empty" in (limits.check("  \n ") or "")
    # the estimate the deck shows follows the speed multiplier
    assert limits.estimate_seconds(limits.WORDS_PER_MINUTE, 1.0) == pytest.approx(60.0)
    assert limits.estimate_seconds(limits.WORDS_PER_MINUTE, 1.2) == pytest.approx(50.0)
    payload = limits.limits_payload()
    assert payload["max_words"] == limits.MAX_WORDS
    assert [v["id"] for v in payload["voices"]] == list(kokoro_tts.VOICE_IDS)


# ---------------------------------------------------------------------------
# narrate (F02) against a fake synthesiser — the real weights never load here


class FakeSynth:
    """A quarter second of sine per word, scaled by speed: deterministic
    durations so the title boundary can be asserted exactly."""

    def __init__(self, fail: Exception | None = None):
        self.calls: list[tuple[str, str, float]] = []
        self.fail = fail

    def synth(self, text: str, voice: str, speed: float) -> np.ndarray:
        if self.fail is not None:
            raise self.fail
        self.calls.append((text, voice, speed))
        n = int(0.25 * limits.word_count(text) * kokoro_tts.SAMPLE_RATE / speed)
        t = np.arange(n) / kokoro_tts.SAMPLE_RATE
        return (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)


def _story_job(text: str = STORY, **story_kw) -> tuple[queue.Job, config.Settings]:
    settings = _story_settings()
    for key, value in story_kw.items():
        assert key in {f.name for f in dataclasses.fields(config.StorySettings)}
        setattr(settings.story, key, value)
    job = queue.create_job("file", "C:/bg.mp4", json.dumps(settings.to_json()))
    story_mod.store(job.dir, text)
    return job, settings


def _wav_seconds(path) -> float:
    with wave.open(str(path), "rb") as wf:
        return wf.getnframes() / wf.getframerate()


def test_narrate_writes_the_wav_and_records_where_the_title_ends():
    job, settings = _story_job()
    fake = FakeSynth()
    stage = narrate_stage.NarrateStage(synth=fake)
    ctx = queue.StageContext(job=job, settings=settings, progress=_noop)
    data = stage.run(ctx)

    assert [c[0] for c in fake.calls] == ["The chair", story_mod.parse(STORY).body]
    assert all(c[1] == "af_heart" and c[2] == 1.0 for c in fake.calls)
    wav = job.dir / narrate_stage.NARRATION_FILE
    assert wav.exists() and data["audio_path"] == str(wav)
    # 2 title words + the gap + 13 body words
    assert data["title_end_sec"] == pytest.approx(0.5 + narrate_stage.TITLE_GAP_SEC, abs=1e-3)
    assert data["duration_sec"] == pytest.approx(0.5 + narrate_stage.TITLE_GAP_SEC + 13 * 0.25, abs=1e-3)
    assert _wav_seconds(wav) == pytest.approx(data["duration_sec"], abs=1e-3)
    assert data["title"] == "The chair" and data["word_count"] == 15
    assert data["settings_used"] == {
        "text_sha256": story_mod.parse(STORY).sha256, "voice": "af_heart", "speed": 1.0,
    }
    # the rail shows a story by its title, not the background's filename
    assert queue.get_job(job.id).title == "The chair"
    assert stage.artifacts_ok(ctx, data) is True


def test_a_voice_or_speed_change_reruns_narrate_and_nothing_changed_reuses_everything():
    job, settings = _story_job()
    stage = narrate_stage.NarrateStage(synth=FakeSynth())
    ctx = queue.StageContext(job=job, settings=settings, progress=_noop)
    data = stage.run(ctx)
    assert stage.artifacts_ok(ctx, data) is True

    other = config.Settings.from_json(settings.to_json())
    other.story.voice = "bm_george"
    assert stage.artifacts_ok(queue.StageContext(job=job, settings=other, progress=_noop), data) is False
    other = config.Settings.from_json(settings.to_json())
    other.story.speed = 1.15
    assert stage.artifacts_ok(queue.StageContext(job=job, settings=other, progress=_noop), data) is False
    # a caption restyle is not the narrator's business
    other = config.Settings.from_json(settings.to_json())
    other.caption_preset = "beast"
    assert stage.artifacts_ok(queue.StageContext(job=job, settings=other, progress=_noop), data) is True
    # a checkpoint from before a future story key existed compares against
    # the factory value (§4 rule 3), not against nothing
    stale = {**data, "settings_used": {"text_sha256": story_mod.parse(STORY).sha256}}
    assert stage.artifacts_ok(ctx, stale) is True
    # the wav going missing is stale, whatever the fingerprint says
    (job.dir / narrate_stage.NARRATION_FILE).unlink()
    assert stage.artifacts_ok(ctx, data) is False


class Counting(queue.Stage):
    schema_version = 1

    def __init__(self, name):
        self.name = name
        self.runs = 0

    def run(self, ctx):
        self.runs += 1
        return {"runs": self.runs, "audio_path": "x"}


def test_a_text_edit_reruns_narrate_and_cascades_to_asr_and_render():
    """§4 rules 1 and 2 for the new stage: the text hash is in its
    fingerprint, and a re-run of narrate invalidates everything after it,
    whatever those stages' own checkpoints say."""
    job, _ = _story_job()
    fake = FakeSynth()
    stages = [narrate_stage.NarrateStage(synth=fake), Counting("asr"), Counting("render")]

    queue.run_stages(job, stages, _noop)
    assert len(fake.calls) == 2 and stages[1].runs == 1 and stages[2].runs == 1
    queue.run_stages(job, stages, _noop)  # nothing changed: everything cached
    assert len(fake.calls) == 2 and stages[1].runs == 1 and stages[2].runs == 1

    story_mod.store(job.dir, STORY + "\nOne more line.")
    queue.run_stages(job, stages, _noop)
    assert len(fake.calls) == 4, "narrate did not re-run on a text edit"
    assert stages[1].runs == 2 and stages[2].runs == 2, "the cascade did not reach asr and render"


def test_narrate_degrades_with_a_described_error_never_a_traceback():
    job, settings = _story_job()
    ctx = queue.StageContext(job=job, settings=settings, progress=_noop)

    broken = narrate_stage.NarrateStage(synth=FakeSynth(fail=kokoro_tts.NarratorUnavailable("no weights")))
    with pytest.raises(queue.StageError) as err:
        broken.run(ctx)
    assert err.value.code == "narrator-unavailable" and "no weights" in str(err.value)

    story_mod.path_in(job.dir).unlink()
    with pytest.raises(queue.StageError) as err:
        narrate_stage.NarrateStage(synth=FakeSynth()).run(ctx)
    assert err.value.code == "story-text-missing"

    story_mod.store(job.dir, "Title\n" + " ".join(["w"] * (limits.MAX_WORDS + 1)))
    with pytest.raises(queue.StageError) as err:
        narrate_stage.NarrateStage(synth=FakeSynth()).run(ctx)
    assert err.value.code == "story-too-long" and str(limits.MAX_WORDS) in str(err.value)

    story_mod.store(job.dir, STORY)
    settings.story.voice = "someone_real"
    with pytest.raises(queue.StageError) as err:
        narrate_stage.NarrateStage(synth=FakeSynth()).run(ctx)
    assert err.value.code == "narrator-unavailable"

    from publikclip_pipeline import errors

    for code in ("story-text-missing", "story-too-long", "narrator-unavailable", "narration-empty"):
        assert code in errors.CATALOG, code


def test_every_offered_voice_has_a_pinned_file():
    from publikclip_pipeline.models import specs

    for voice_id, _label in kokoro_tts.VOICES:
        assert voice_id in specs.KOKORO_VOICES
        assert specs.KOKORO_VOICES[voice_id].sha256
    assert kokoro_tts.is_present("af_heart") is False  # fresh home: disk truth
    with pytest.raises(ValueError):
        kokoro_tts.specs_for("someone_real")


# ---------------------------------------------------------------------------
# asr hears the prior it was built for (F04)


def test_asr_reads_the_prior_it_was_built_for(tmp_path):
    from publikclip_pipeline.asr.stage import AsrStage

    job, settings = _story_job()
    scoped = queue._ctx_for(
        queue.StageContext(job=job, settings=settings, progress=_noop), "asr",
        {"ingest": {"audio_path": str(tmp_path / "audio16k.wav")}},
    )
    with pytest.raises(queue.StageError) as err:
        AsrStage(source="narrate").run(scoped)
    assert "narrate" in str(err.value) and err.value.code == "prior-stage-missing"

    scoped = queue._ctx_for(
        queue.StageContext(job=job, settings=settings, progress=_noop), "asr",
        {"narrate": {"audio_path": str(tmp_path / "gone.wav")}},
    )
    with pytest.raises(queue.StageError) as err:
        AsrStage(source="narrate").run(scoped)
    assert "re-run narrate" in str(err.value)
    # the clips chain's asr still names ingest
    with pytest.raises(queue.StageError) as err:
        AsrStage().run(scoped)
    assert "ingest" in str(err.value)


# ---------------------------------------------------------------------------
# the CLI: the story reaches the job as a file, and nowhere else


def _last_json(capsys) -> dict:
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def test_jobs_create_copies_the_story_into_the_job_and_refuses_the_rest(tmp_path, capsys):
    from publikclip_pipeline import cli

    txt = tmp_path / "story.txt"
    txt.write_text(STORY, encoding="utf-8")
    rc = cli.main([
        "jobs", "create", "C:/bg.mp4", "--mode", "stories", "--story-file", str(txt),
        "--voice", "bm_george", "--speed", "1.1",
    ])
    assert rc == 0
    job = queue.get_job(_last_json(capsys)["job_id"])
    assert job.mode == "stories"
    stored = story_mod.load(job.dir)
    assert stored.title == "The chair" and stored.sha256 == story_mod.parse(STORY).sha256
    saved = config.Settings.from_json(json.loads(job.settings_json))
    assert saved.story.voice == "bm_george" and saved.story.speed == 1.1
    # the text is in the job dir and NOT in the snapshot
    assert "chair" not in job.settings_json

    assert cli.main(["jobs", "create", "C:/bg.mp4", "--mode", "stories"]) == 2
    assert "--story-file" in _last_json(capsys)["error"]
    assert cli.main(["jobs", "create", "C:/bg.mp4", "--mode", "stories", "--story-file", str(tmp_path / "no.txt")]) == 2
    assert "not found" in _last_json(capsys)["error"]
    txt.write_text("Title\n" + " ".join(["w"] * (limits.MAX_WORDS + 1)), encoding="utf-8")
    assert cli.main(["jobs", "create", "C:/bg.mp4", "--mode", "stories", "--story-file", str(txt)]) == 2
    assert str(limits.MAX_WORDS) in _last_json(capsys)["error"]
    # nothing above left a pending job behind for the queue to spawn
    assert queue.next_pending().id == job.id
    queue.cancel_pending(job.id)
    assert queue.next_pending() is None
    # a clips job needs no story and takes none
    assert cli.main(["jobs", "create", "C:/x.mp4", "--story-file", str(txt)]) == 0
    assert not story_mod.path_in(queue.get_job(_last_json(capsys)["job_id"]).dir).exists()


def test_story_limits_verb_prints_the_numbers_the_gate_uses(capsys):
    from publikclip_pipeline import cli

    assert cli.main(["settings", "story-limits"]) == 0
    out = _last_json(capsys)
    assert out["max_words"] == limits.MAX_WORDS and out["warn_words"] == limits.WARN_WORDS
    assert out["words_per_minute"] == limits.WORDS_PER_MINUTE
    assert out["default_voice"] == kokoro_tts.DEFAULT_VOICE


def test_remember_background_saves_a_real_file_only(tmp_path, capsys):
    from publikclip_pipeline import cli

    bg = tmp_path / "parkour.mp4"
    bg.write_bytes(b"x")
    assert cli.main(["settings", "remember-background", str(bg)]) == 0
    assert _last_json(capsys)["defaults"]["story"]["background"] == str(bg)
    assert config.load_defaults().story.background == str(bg)
    assert cli.main(["settings", "remember-background", str(tmp_path / "gone.mp4")]) == 1
    assert config.load_defaults().story.background == str(bg)


def test_the_narrator_is_a_setup_item_for_stories_only():
    from publikclip_pipeline import setup as setup_mod

    clips_ids = [i.id for i in setup_mod.items(config.Settings())]
    story_ids = [i.id for i in setup_mod.items(_story_settings(), mode="stories")]
    assert "kokoro" not in clips_ids, "onboarding must not grow the narrator"
    assert "kokoro" in story_ids
    assert set(story_ids) == {"ffmpeg", "whisper", "vad", "align-en", "kokoro"}
    assert setup_mod.status(_story_settings(), mode="stories")["total_missing_bytes"] > 0


def test_a_story_job_is_charged_for_its_narration_and_video_by_word_count():
    from publikclip_pipeline.jobs import disk

    job, settings = _story_job(" ".join(["word"] * 300))
    needs, unknown = disk.gather(job, settings)
    by_label = {n.label: n for n in needs}
    assert "the story video" in by_label and "narration audio" in by_label
    seconds = limits.estimate_seconds(300, 1.0)
    assert by_label["narration audio"].low == int(seconds * kokoro_tts.SAMPLE_RATE * 2) + disk.WAV_HEADER_BYTES
    assert by_label["the story video"].high == int(seconds * disk.RENDER_BPS_HIGH)
    assert not any("story video" in u for u in unknown)


# ---------------------------------------------------------------------------
# The chain itself


def test_the_stories_chain_is_ingest_narrate_asr_render():
    from publikclip_pipeline import cli
    from publikclip_pipeline.asr.stage import AsrStage
    from publikclip_pipeline.ingest.stage import IngestStage

    assert chains.chain_for("stories") == ("ingest", "narrate", "asr", "render")
    built = cli._stages("stories")
    assert [s.name for s in built] == list(chains.STORY_CHAIN)
    assert isinstance(built[0], IngestStage) and built[0].needs_audio is False
    assert isinstance(built[2], AsrStage) and built[2].source == "narrate"
    assert isinstance(built[3], story_render.StoryRenderStage)
    assert "narrate" in chains.ALL_STAGES


def test_resume_info_lists_the_story_chain_and_the_picker_gate_holds(capsys):
    from publikclip_pipeline import cli

    job, _ = _story_job()
    queue.write_checkpoint(job, "ingest", 1, {"probe": {"duration_sec": 5.0}})
    queue.set_job_status(job.id, "failed", "narrate: boom")
    (job.dir / queue.ERROR_FILE).write_text(
        json.dumps({"code": "narrator-unavailable", "cause": "boom", "stage": "narrate"}),
        encoding="utf-8",
    )
    info = queue.resume_info(queue.get_job(job.id))
    assert [s["name"] for s in info["stages"]] == list(chains.STORY_CHAIN)
    assert info["default_stage"] == "narrate"
    assert {s["name"]: s["status"] for s in info["stages"]}["ingest"] == "done"
    assert all(s["estimate_sec"] is None for s in info["stages"])  # story jobs are not profiled

    # argparse accepts narrate now, and cmd_resume gates on the job's chain
    assert cli.main(["resume", job.id, "--from-stage", "diarize"]) == 2
    assert "not a stage of this stories job" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        cli.main(["resume", job.id, "--from-stage", "karaoke"])


def test_diagnose_lists_a_story_jobs_own_stages():
    from publikclip_pipeline import diagnose

    job, _ = _story_job()
    stages = diagnose._stages_file(job)
    assert list(stages) == list(chains.STORY_CHAIN)
    assert set(chains.ALL_STAGES) <= diagnose.MANIFEST["stages.json"]


# ---------------------------------------------------------------------------
# The card (F05) and the one-word captions (F04)


def test_the_story_preset_is_one_word_at_a_time_through_the_same_chunker():
    preset = ass_mod.resolve_preset(story_render.STORY_PRESET)
    assert preset.max_words == 1
    words = [ass_mod.Word(f"w{i}", i * 0.3, i * 0.3 + 0.25) for i in range(5)]
    chunks = ass_mod.chunk_words(words, preset.max_words, preset.pause_break)
    assert [len(c.words) for c in chunks] == [1, 1, 1, 1, 1]
    assert ass_mod.chunk_words(words) != chunks  # the default preset groups them


def test_the_card_is_the_apps_own_design_and_leaves_when_the_title_ends():
    preset = ass_mod.resolve_preset("classic")
    styles, events = story_card.overlay(preset, "The chair", 2.4)
    assert "Style: StoryTitle,Inter" in styles and "Style: StoryShape" in styles
    lines = [line for line in events.splitlines() if line.startswith("Dialogue")]
    assert len(lines) == 3
    assert all("0:00:00.00,0:00:02.40" in line for line in lines)
    assert lines[0].startswith("Dialogue: 3,") and "\\p1" in lines[0] and "\\1a&H33&" in lines[0]
    assert lines[1].startswith("Dialogue: 4,") and "\\1c&H00D7FF&" in lines[1]  # the preset's active colour
    assert lines[2].startswith("Dialogue: 5,") and lines[2].endswith("The chair")
    assert "\\pos(540,960)" in lines[2] and "\\q0" in lines[2] and "\\fad(" in lines[2]
    # nothing that belongs to another platform, nothing invented
    for forbidden in ("upvote", "comment", "share", "u/", "r/", "👍", "❤"):
        assert forbidden not in events
    assert story_card.overlay(preset, "", 2.4) == ("", "")
    assert story_card.overlay(preset, "The chair", 0.0) == ("", "")
    assert story_card.title_size("short") > story_card.title_size("x" * 100)
    assert story_card.rounded_rect(0, 0, 10, 10, 20).startswith("m 5 0 ")


def test_caption_words_start_after_the_title():
    segments = [{"words": [
        {"word": "The", "start": 0.0, "end": 0.2}, {"word": "chair", "start": 0.25, "end": 0.5},
        {"word": "Nobody", "start": 0.97, "end": 1.3}, {"word": "moved", "start": 1.4, "end": 1.7},
    ]}]
    words = story_render.caption_words(segments, 1.0)
    assert [w.text for w in words] == ["Nobody", "moved"]
    assert words[0].start == 0.97


# ---------------------------------------------------------------------------
# The story render (F03): the command, the fingerprint, real pixels


def test_the_story_command_loops_mutes_and_covers_through_the_shared_geometry(tmp_path, monkeypatch):
    seen: dict = {}

    def fake_run(args, **kw):
        seen["args"] = args

        class P:
            returncode = 0
            stderr = ""
        return P()

    monkeypatch.setattr(renderer.subprocess, "run", fake_run)
    monkeypatch.setattr(renderer, "video_encoder_args", lambda hw: ["-c:v", "libx264"])
    renderer.render_story("bg.mp4", "narr.wav", tmp_path / "out.mp4", 12.345, tmp_path / "c.ass", None)
    args = seen["args"]
    assert args[args.index("-stream_loop") + 1] == "-1"          # looped when short
    assert args[args.index("-t") + 1] == "12.345"                 # trimmed when long
    assert "-map" in args and args[args.index("-map") + 1] == "0:v:0"
    assert args[args.index("-map", args.index("-map") + 1) + 1] == "1:a:0"  # background audio never mapped
    vf = args[args.index("-vf") + 1]
    assert vf.startswith(renderer.cover_vf() + ",setsar=1")
    assert "subtitles=filename=" in vf
    # the same geometry the blur fill's backdrop uses, verbatim
    assert renderer.cover_vf() in renderer.scale_pad_vf(1920, 1080, "blur")[0]
    assert "apad" in args[args.index("-af") + 1]


def _story_prior(job, tmp_path, seconds: float = 3.5):
    """ingest + narrate + asr checkpoints for a rendered story: a silent
    16:9 background, a sine narration, and fake word timings."""
    bg = _silent_video(tmp_path / "bg.mp4", seconds=2.0)  # shorter than the narration: must loop
    wav = job.dir / narrate_stage.NARRATION_FILE
    t = np.arange(int(seconds * kokoro_tts.SAMPLE_RATE)) / kokoro_tts.SAMPLE_RATE
    narrate_stage.write_wav(wav, (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32))
    words = [{"word": w, "start": 0.2 + i * 0.4, "end": 0.5 + i * 0.4} for i, w in enumerate(
        ["The", "chair", "Nobody", "had", "moved", "the", "chair"])]
    return {
        "ingest": {"media_path": str(bg), "probe": {"width": 640, "height": 360, "has_audio": False}},
        "narrate": {"audio_path": str(wav), "duration_sec": seconds, "title": "The chair",
                    "title_end_sec": 1.0},
        "asr": {"segments": [{"words": words}]},
    }


def test_the_story_render_fingerprint_covers_what_it_bakes_in(tmp_path):
    job, settings = _story_job()
    stage = story_render.StoryRenderStage()
    ctx = queue.StageContext(job=job, settings=settings, progress=_noop)
    out = job.dir / "clips" / "story.mp4"
    out.parent.mkdir()
    out.write_bytes(b"x")
    data = {"story": True, "outputs": [{"clip": 0, "story": True, "path": str(out), "duration": 4.1}],
            **story_render._fingerprint(ctx)}
    assert stage.artifacts_ok(ctx, data) is True
    # a clip checkpoint never serves a story job
    assert stage.artifacts_ok(ctx, {**data, "story": False}) is False
    for change in (
        lambda s: setattr(s, "caption_preset", "beast"),
        lambda s: setattr(s, "lufs_target", -16.0),
        lambda s: setattr(s.watermark, "text", "@me"),
        lambda s: s.captions.overrides.update({"size": 40}),
    ):
        other = config.Settings.from_json(settings.to_json())
        change(other)
        assert stage.artifacts_ok(queue.StageContext(job=job, settings=other, progress=_noop), data) is False
    # and things the story does not read leave it alone
    other = config.Settings.from_json(settings.to_json())
    other.camera.gameplay_amount = 1.0
    other.clips.select_count = 3
    assert stage.artifacts_ok(queue.StageContext(job=job, settings=other, progress=_noop), data) is True
    out.unlink()
    assert stage.artifacts_ok(ctx, data) is False


def test_the_story_render_makes_one_verified_vertical_file(tmp_path):
    """Real pixels through the shared encoder path (§3's synthetic way): a
    2 s silent 16:9 background under 3.5 s of narration renders a 1080x1920
    file of the narration's length plus the tail, captioned one word at a
    time after the card."""
    job, settings = _story_job()
    settings.caption_preset = story_render.STORY_PRESET
    ctx = queue._ctx_for(
        queue.StageContext(job=job, settings=settings, progress=_noop), "render",
        _story_prior(job, tmp_path),
    )
    data = story_render.StoryRenderStage().run(ctx)
    assert data["story"] is True and len(data["outputs"]) == 1
    out = data["outputs"][0]
    assert out["story"] is True and out["clip"] == 0 and out["title"] == "The chair"
    assert out["words"] == 5  # the two title words are the card's, not captions
    check = renderer.verify_output(Path(out["path"]), 3.5 + story_render.TAIL_SEC)
    assert check["ok"], check
    assert check["width"] == 1080 and check["height"] == 1920
    doc = Path(out["ass"]).read_text(encoding="utf-8")
    assert "StoryTitle" in doc and "THE CHAIR" in doc  # the story preset is uppercase
    assert doc.count("Cap,,0,0,0,") == 5  # one Dialogue per word: one-word captions
    assert story_render.StoryRenderStage().artifacts_ok(ctx, data) is True


# ---------------------------------------------------------------------------
# D-20: the two guards on the clip-keyed readers of render.json


def test_invalidating_render_on_a_story_job_drops_the_story_file(tmp_path):
    job, _ = _story_job()
    out = job.dir / "clips" / "story.mp4"
    out.parent.mkdir()
    out.write_bytes(b"story")
    queue.write_checkpoint(job, "render", 1, {
        "story": True, "outputs": [{"clip": 0, "story": True, "path": str(out), "duration": 4.0}],
    })
    assert queue.invalidate_stage(job, "render") == {"stage": "render", "dropped_clips": [0]}
    assert not out.exists()
    assert queue.checkpoint_path(job, "render").exists()  # the file, never the checkpoint
    # and a story entry is never mistaken for an adoptable clip
    out.write_bytes(b"story")
    assert render_stage._previous_outputs(job.dir) == {}


def test_a_story_killed_mid_encode_loses_only_its_truncated_file(monkeypatch):
    job, _ = _story_job()
    out = job.dir / "clips" / "story.mp4"
    out.parent.mkdir()
    out.write_bytes(b"truncated")
    queue.write_checkpoint(job, "render", 1, {
        "story": True, "outputs": [{"clip": 0, "story": True, "path": str(out), "duration": 4.0}],
    })
    queue.mark_stage(job.id, "render", "running", 1)
    queue.set_job_status(job.id, "running")
    monkeypatch.setattr(
        "publikclip_pipeline.render.renderer.verify_output",
        lambda out_path, expected_duration: {"ok": False},
    )
    assert queue.mark_cancelled(job.id)["marked"] is True
    assert not out.exists()
    assert queue.checkpoint_path(job, "render").exists()

    # an intact story survives the same kill
    out.write_bytes(b"whole")
    queue.set_job_status(job.id, "running")
    queue.mark_stage(job.id, "render", "running", 1)
    monkeypatch.setattr(
        "publikclip_pipeline.render.renderer.verify_output",
        lambda out_path, expected_duration: {"ok": True},
    )
    assert queue.mark_cancelled(job.id)["marked"] is True
    assert out.exists()
