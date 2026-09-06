"""E20 / D-19: two stage chains over one machine.

The contract these pin: the chain table (chains.py) is the light-import
truth every enumerator reads, `cli._stages(mode)` builds exactly what the
table names for EVERY chain (a loop, not a single equality — a second
chain that drifted from its table would let the resume picker offer a
stage the run never executes), the mode lives in the settings snapshot
and a snapshot from before the field existed is a clips job (§4 rule 3
applied to the chain itself — this protects every job on disk), and an
unknown mode is refused rather than guessed."""

import json

import pytest

from publikclip_pipeline import chains, config
from publikclip_pipeline.jobs import queue


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("PUBLIKCLIP_HOME", str(tmp_path / "home"))
    yield


def test_every_chain_builds_the_stages_its_table_names():
    from publikclip_pipeline import cli

    assert chains.CHAINS, "no chains registered"
    for mode, names in chains.CHAINS.items():
        built = tuple(s.name for s in cli._stages(mode))
        assert built == names, f"{mode}: _stages() builds {built}, the table says {names}"


def test_a_snapshot_written_before_the_mode_existed_is_a_clips_job():
    # Every settings.json on disk today lacks the key. It must read as the
    # clips chain everywhere the mode is consulted — the deserializer, the
    # Job accessor, and the chain lookup — or an hour of checkpoints would
    # be run through the wrong chain on the next resume.
    legacy = config.Settings().to_json()
    del legacy["mode"]
    assert config.Settings.from_json(legacy).mode == "clips"
    assert config.Settings.from_json({**legacy, "mode": ""}).mode == "clips"

    job = queue.create_job("file", "C:/x.mp4", json.dumps(legacy))
    assert job.mode == "clips"
    assert chains.chain_for(job.mode) == chains.CLIPS_CHAIN
    assert chains.chain_for(None) == chains.CLIPS_CHAIN
    assert chains.chain_for("") == chains.CLIPS_CHAIN


def test_the_mode_round_trips_through_the_snapshot():
    settings = config.Settings()
    settings.mode = "clips"
    assert config.Settings.from_json(settings.to_json()).mode == "clips"
    # a corrupt row does not crash the accessor — it is a clips job
    job = queue.create_job("file", "C:/x.mp4", json.dumps(config.Settings().to_json()))
    job.settings_json = "{not json"
    assert job.mode == "clips"


def test_an_unknown_mode_is_refused_not_guessed():
    with pytest.raises(ValueError, match="unknown mode"):
        chains.chain_for("karaoke")
    from publikclip_pipeline import cli

    with pytest.raises(ValueError):
        cli._stages("karaoke")


def test_all_stages_is_the_union_in_first_appearance_order():
    seen: list[str] = []
    for chain in chains.CHAINS.values():
        for name in chain:
            if name not in seen:
                seen.append(name)
    assert chains.ALL_STAGES == tuple(seen)
    assert len(set(chains.ALL_STAGES)) == len(chains.ALL_STAGES)


def test_the_enqueue_flag_sets_the_job_mode(capsys):
    """`jobs create --mode` lands on the snapshot through the same
    `_apply_setting_flags` every other deck control uses, and without the
    flag the saved default governs."""
    from publikclip_pipeline import cli

    assert cli.main(["jobs", "create", "C:/nowhere/a.mp4", "--mode", "clips"]) == 0
    job_id = json.loads(capsys.readouterr().out.strip().splitlines()[-1])["job_id"]
    assert queue.get_job(job_id).mode == "clips"

    with pytest.raises(SystemExit):
        cli.main(["jobs", "create", "C:/nowhere/a.mp4", "--mode", "karaoke"])


def test_resume_takes_no_mode_flag():
    """A job's checkpoints belong to the chain that wrote them: resume
    must not be able to re-chain a job."""
    from publikclip_pipeline import cli

    with pytest.raises(SystemExit):
        cli.main(["resume", "some-job", "--mode", "clips"])


def test_the_job_event_carries_the_mode(monkeypatch, capsys):
    """The deck draws the running chain's rows from the job event — the one
    place a job start is observed (§5.12) — so the mode must ride it."""
    from publikclip_pipeline import cli, hardware_profile
    from publikclip_pipeline.jobs import disk
    from publikclip_pipeline.render import ffmpeg_bin

    job = queue.create_job("file", "C:/x.mp4", json.dumps(config.Settings().to_json()))
    monkeypatch.setattr(disk, "preflight", lambda job: {"action": "ok", "message": ""})
    monkeypatch.setattr(ffmpeg_bin, "ensure_capable", lambda progress=None: True)
    monkeypatch.setattr(queue, "run_stages", lambda job, stages, emit: {})
    monkeypatch.setattr(hardware_profile, "update_after_job", lambda job_id, started: None)
    assert cli._execute(job, jsonl=True) == 0
    first = json.loads(capsys.readouterr().out.strip().splitlines()[0])
    assert first["event"] == "job"
    assert first["job_id"] == job.id
    assert first["mode"] == "clips"
