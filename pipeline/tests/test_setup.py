"""E1-F01 setup flow: presence is disk truth, downloads resume, one failure
never hides the rest.

The foreign-downloader items (whisper, silero, align) are exercised only at
the presence-check level here — their fetchers reach real networks and real
model hubs, which §3 forbids in tests. The registry path, which we own end
to end, is exercised for the property the requirement names: an interrupted
download resumes at its byte offset instead of restarting.
"""

from __future__ import annotations

import dataclasses
import hashlib

import pytest

from publikclip_pipeline import config
from publikclip_pipeline import setup as setup_mod
from publikclip_pipeline.models import registry, specs


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("PUBLIKCLIP_HOME", str(tmp_path))
    # An external HF_HOME/TORCH_HOME would redirect presence checks off the
    # tmp home (they honour the same env the ASR stage does).
    monkeypatch.delenv("HF_HOME", raising=False)
    monkeypatch.delenv("TORCH_HOME", raising=False)
    return tmp_path


def _model_items(settings=None):
    """Every item except ffmpeg, whose presence depends on the machine the
    test runs on (a system ffmpeg with libass makes it 'present')."""
    return [i for i in setup_mod.items(settings) if i.id != "ffmpeg"]


def test_every_model_item_is_absent_on_a_fresh_machine_and_flips_per_file(home):
    for item in _model_items():
        assert not item.present(), f"{item.id} claimed present on an empty home"

    # Materialise each item the way its downloader would, one at a time.
    (home / "models" / "hf" / "hub"
     / "models--mobiuslabsgmbh--faster-whisper-large-v3-turbo" / "snapshots" / "abc"
     ).mkdir(parents=True)
    (home / "models" / "hf" / "hub"
     / "models--mobiuslabsgmbh--faster-whisper-large-v3-turbo" / "snapshots" / "abc"
     / "model.bin").write_bytes(b"w")
    (home / "models" / "torch" / "hub" / "checkpoints").mkdir(parents=True)
    (home / "models" / "torch" / "hub" / "checkpoints"
     / "wav2vec2_fairseq_base_ls960_asr_ls960.pth").write_bytes(b"a")
    (home / "models" / "torch" / "hub" / "snakers4_silero-vad_master").mkdir(parents=True)
    for spec in (specs.CAMPPLUS, specs.PANNS_CNN14_MAX, specs.ULTRAFACE,
                 specs.LR_ASD_FRONTEND, specs.LR_ASD_BACKEND):
        path = registry.model_path(spec)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")

    for item in _model_items():
        assert item.present(), f"{item.id} still absent with its files on disk"


def test_laughter_is_included_only_when_the_user_enabled_it(home):
    # Settings is a plain dataclass: assigning to a field that was never
    # declared would create it silently and this test would then pass while
    # testing nothing (§7) — so prove the field is real first.
    assert "laughter_specialist" in {f.name for f in dataclasses.fields(config.Settings)}
    off = config.Settings()
    on = config.Settings()
    on.laughter_specialist = True
    assert "laughter" not in [i.id for i in setup_mod.items(off)]
    assert "laughter" in [i.id for i in setup_mod.items(on)]


def test_ser_is_not_a_setup_item(home):
    # Deliberate exclusion, not an oversight: the SER loader has never
    # succeeded on the reference machine (every job on disk fell back to
    # dsp-proxy), so prefetching its 378 MB would be waste until the loader
    # is fixed. See the setup module docstring; remove this pin only when
    # setup adopts a demonstrably loading SER.
    ids = [i.id for i in setup_mod.items(config.Settings())]
    assert not any("ser" in i for i in ids)
    assert set(ids) >= {"whisper", "vad", "align-en", "campplus", "panns", "vision"}


def test_total_missing_bytes_counts_only_what_is_missing(home):
    before = setup_mod.status(config.Settings())
    assert before["total_missing_bytes"] > 1_500_000_000  # whisper alone guarantees this

    path = registry.model_path(specs.PANNS_CNN14_MAX)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")
    after = setup_mod.status(config.Settings())
    assert (
        before["total_missing_bytes"] - after["total_missing_bytes"]
        == specs.PANNS_CNN14_MAX.approx_mb * 1_000_000
    )


def _fake_item(item_id: str, present_box: list, fetch) -> setup_mod.SetupItem:
    return setup_mod.SetupItem(item_id, item_id, 10, lambda: present_box[0], fetch)


def test_run_skips_present_items_and_one_failure_does_not_stop_the_rest(home):
    calls: list[str] = []
    events: list[dict] = []

    done_box = [True]
    fail_box = [False]
    ok_box = [False]

    def failing(progress):
        calls.append("broken")
        raise RuntimeError("mirror down")

    def succeeding(progress):
        calls.append("fresh")
        ok_box[0] = True  # the fetch is what puts the files on disk

    result = setup_mod.run(
        events.append,
        item_list=[
            _fake_item("cached", done_box, lambda p: calls.append("cached")),
            _fake_item("broken", fail_box, failing),
            _fake_item("fresh", ok_box, succeeding),
        ],
    )

    assert calls == ["broken", "fresh"], "a present item must not be re-fetched"
    assert result["ok"] is False
    assert result["failures"] == [{"item": "broken", "error": "mirror down"}]
    states = {(e["item"], e["state"]) for e in events}
    assert ("cached", "done") in states
    assert ("broken", "failed") in states
    assert ("fresh", "done") in states


def test_run_reports_a_fetch_that_left_nothing_behind(home):
    # A fetcher that returns cleanly while the job would still find nothing
    # must read as failed — a green row over a broken first job is the §5.2
    # lie in download form.
    still_absent = [False]
    result = setup_mod.run(
        lambda e: None,
        item_list=[_fake_item("hollow", still_absent, lambda p: None)],
    )
    assert result["ok"] is False
    assert result["failures"][0]["item"] == "hollow"


class _FakeResponse:
    def __init__(self, status_code: int, body: bytes):
        self.status_code = status_code
        self.headers = {"content-length": str(len(body))}
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def iter_bytes(self):
        yield self._body


def test_interrupted_registry_download_resumes_instead_of_restarting(home, monkeypatch):
    payload = b"0123456789" * 10  # 100 bytes
    spec = registry.ModelSpec(
        name="resume-test", filename="weights.bin", url="https://example.invalid/w.bin",
        sha256=hashlib.sha256(payload).hexdigest(),
    )
    dest = registry.model_path(spec)
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    part.write_bytes(payload[:40])  # the state a killed download leaves

    seen: list[dict] = []

    def fake_stream(method, url, headers=None, **kwargs):
        seen.append(dict(headers or {}))
        # 206 with ONLY the remainder: if ensure restarted from zero it
        # would append these 60 bytes onto a stale 40 and fail the sha.
        return _FakeResponse(206, payload[40:])

    monkeypatch.setattr(registry.httpx, "stream", fake_stream)
    registry.ensure(spec, lambda f, m: None)

    assert seen == [{"Range": "bytes=40-"}], "resume must ask for the remainder, not the file"
    assert dest.read_bytes() == payload
    assert not part.exists()
