"""E14-F03 / T-15: the diagnostic bundle. Two guarantees, each with its
own net: nothing secret or content-naming survives into any file (the
test_secret_leaks.py mould — a job soaked in a key, a token, home paths,
a source name and prose keywords yields a bundle containing none of
them), and nothing undeclared gets written (every curated file's keys
must appear in diagnose.MANIFEST, so a future addition is a declaration,
not a drive-by)."""

import json
import zipfile
from pathlib import Path

import pytest

from publikclip_pipeline import config, diagnose
from publikclip_pipeline.jobs import queue

FAKE_KEY = "AIzaFAKEFAKEFAKEFAKEFAKEFAKEFAKE123"
FAKE_TOKEN = "IGQVJfaketokenfaketokenfaketoken"
TITLE = "Unreleased Trailer Final"
SOURCE = r"C:\Users\somebody\Videos\Unreleased Trailer Final.mp4"


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("PUBLIKCLIP_HOME", str(home))
    home.mkdir(parents=True, exist_ok=True)
    monkeypatch.delenv("HF_HOME", raising=False)
    monkeypatch.delenv("TORCH_HOME", raising=False)
    yield home


def _soaked_job(home) -> queue.Job:
    (home / "secrets.json").write_text(
        json.dumps({"gemini_api_key": FAKE_KEY}), encoding="utf-8"
    )
    (home / "instagram.json").write_text(
        json.dumps({"access_token": FAKE_TOKEN}), encoding="utf-8"
    )
    settings = config.Settings()
    settings.titles.keywords = "secret project skyfall"
    job = queue.create_job("file", SOURCE, json.dumps(settings.to_json()))
    queue.set_job_status(job.id, "failed", f"ingest: File not found: {SOURCE}")
    queue.write_checkpoint(
        job, "ingest", 1,
        {
            "media_path": SOURCE,
            "title": TITLE,
            "probe": {
                "duration_sec": 3600.0, "width": 1920, "height": 1080, "fps": 30.0,
                "vfr": False, "start_time": 0.0, "video_codec": "h264", "has_audio": True,
            },
        },
    )
    (job.dir / queue.ERROR_FILE).write_text(
        json.dumps(
            {
                "code": "source-file-missing",
                "cause": f"File not found: {SOURCE}",
                "actions": ["x"],
                "stage": "ingest",
                "detail": f"key={FAKE_KEY} while opening {str(Path.home() / 'x')}",
            }
        ),
        encoding="utf-8",
    )
    return queue.get_job(job.id)


def _bundle_texts(job) -> dict[str, str]:
    result = diagnose.build_bundle(job)
    out: dict[str, str] = {}
    with zipfile.ZipFile(result["path"]) as zf:
        for name in zf.namelist():
            out[name] = zf.read(name).decode("utf-8")
    return out


def test_nothing_secret_or_content_naming_survives_into_any_file(isolated_home):
    texts = _bundle_texts(_soaked_job(isolated_home))
    assert len(texts) >= 8
    everything = "\n".join(texts.values())
    # secrets and identity — T-13's redact(), reused not reimplemented
    assert FAKE_KEY not in everything
    assert FAKE_TOKEN not in everything
    assert str(Path.home()) not in everything
    assert Path.home().as_posix() not in everything
    # the fourth category: the user's content itself. Somebody cutting
    # unreleased footage must be able to send this file.
    assert "Unreleased" not in everything
    assert "somebody" not in everything
    assert "skyfall" not in everything
    assert "[removed]" in everything  # masked, not silently dropped


def test_the_shape_survives_even_though_the_content_does_not(isolated_home):
    texts = _bundle_texts(_soaked_job(isolated_home))
    job_file = json.loads(texts["job.json"])
    # the content-neutral half that actually diagnoses: source SHAPE
    assert job_file["probe"]["duration_sec"] == 3600.0
    assert job_file["probe"]["video_codec"] == "h264"
    assert job_file["source_type"] == "file"
    assert "source" not in job_file  # the URL/path field itself never rides
    stages = json.loads(texts["stages.json"])
    assert stages["ingest"]["checkpoint"] is True
    error = json.loads(texts["error.json"])
    assert error["code"] == "source-file-missing"  # the failure stays legible
    manifest = json.loads(texts["manifest.json"])
    assert manifest["bundle_format"] == diagnose.BUNDLE_FORMAT
    assert manifest["pipeline_version"]
    assert "before you send" in texts["README.txt"]  # the inspectability promise


def _keys_at_all_depths(node) -> set[str]:
    out: set[str] = set()
    if isinstance(node, dict):
        for key, value in node.items():
            out.add(key)
            out |= _keys_at_all_depths(value)
    elif isinstance(node, list):
        for value in node:
            out |= _keys_at_all_depths(value)
    return out


def test_every_field_the_bundler_writes_is_a_declared_one(isolated_home):
    # A future addition must be declared in MANIFEST (and therefore argued
    # in review), not slipped into a payload dict.
    texts = _bundle_texts(_soaked_job(isolated_home))
    for name, text in texts.items():
        assert name in diagnose.MANIFEST, f"undeclared file in the bundle: {name}"
        allowed = diagnose.MANIFEST[name]
        if allowed == "*":
            continue
        keys = _keys_at_all_depths(json.loads(text))
        undeclared = keys - allowed
        assert not undeclared, f"{name} writes undeclared fields: {sorted(undeclared)}"


def test_transcript_shaped_checkpoint_data_never_rides(isolated_home):
    job = _soaked_job(isolated_home)
    queue.write_checkpoint(
        job, "asr", 1,
        {
            "language": "en", "model": "large-v3-turbo", "compute_type": "int8",
            "device": "cpu", "align_device": "cpu",
            "segments": [{"text": "the user's actual words about skyfall"}],
        },
    )
    texts = _bundle_texts(job)
    everything = "\n".join(texts.values())
    assert "actual words" not in everything
    assert "segments" not in json.loads(texts["results.json"])["asr"]
    assert json.loads(texts["results.json"])["asr"]["language"] == "en"


def test_bundle_lands_in_the_job_dir_by_default_and_honours_out(isolated_home, tmp_path):
    job = _soaked_job(isolated_home)
    default = diagnose.build_bundle(job)
    assert Path(default["path"]).parent == job.dir
    chosen = tmp_path / "elsewhere.zip"
    assert diagnose.build_bundle(job, chosen)["path"] == str(chosen)
    assert chosen.exists()
