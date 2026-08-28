"""E1-F07 / T-12: the disk pre-flight — estimate arithmetic, the two-volume
case, unknown-never-refuses (§5.9), and what "cannot start" means for the
queue. The policy tests matter most: blocking by leaving a job 'pending'
would make the shell's auto-advance respawn it in a loop, so 'blocked'
must mean 'failed with the numbers in its error, resumable for free'."""

import json
from pathlib import Path

import pytest

from publikclip_pipeline import config
from publikclip_pipeline.jobs import disk, queue


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("PUBLIKCLIP_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("HF_HOME", raising=False)
    monkeypatch.delenv("TORCH_HOME", raising=False)
    yield


def _settings_json() -> str:
    return json.dumps(config.Settings().to_json())


# ---------------------------------------------------------------------------
# The estimate's arithmetic


def test_wav_estimate_is_exact_from_duration():
    # 16 kHz mono s16: the one component that is arithmetic, not a guess.
    assert disk.wav_need(3600.0) == 3600 * config.AUDIO_SR * 2 + disk.WAV_HEADER_BYTES


def test_clip_estimate_is_a_range_that_scales_with_the_settings():
    clips = config.ClipSettings()
    low, high = disk.clips_need(clips)
    assert low == int(clips.select_count * clips.target_len * disk.RENDER_BPS_LOW)
    assert high == int(clips.select_count * clips.max_len * disk.RENDER_BPS_HIGH)
    assert low < high
    doubled = config.ClipSettings(select_count=clips.select_count * 2)
    assert disk.clips_need(doubled) == (low * 2, high * 2)


def test_url_estimate_trusts_yt_dlp_sizes_only_when_its_pick_matches_ours():
    # yt-dlp's -J reports sizes for its DEFAULT format pick. At <=1080p that
    # is what download() will fetch, so the report bounds the range tightly.
    raw = {
        "requested_formats": [
            {"filesize": 800_000_000, "height": 1080},
            {"filesize_approx": 50_000_000},
        ]
    }
    low, high = disk.url_source_need(raw, 3600.0)
    assert low == int(850_000_000 * 0.9)
    assert high == int(850_000_000 * 1.1)

    # Above the cap the report describes a bigger file than DOWNLOAD_FORMAT
    # will fetch: usable as the high end only, never as the confident low.
    raw_4k = {"requested_formats": [{"filesize": 8_000_000_000, "height": 2160}]}
    low, high = disk.url_source_need(raw_4k, 3600.0)
    assert low == int(3600 * disk.URL_BPS_LOW)
    assert high == 8_000_000_000

    # No sizes at all: the duration heuristic, presented as the range it is.
    low, high = disk.url_source_need({}, 3600.0)
    assert (low, high) == (int(3600 * disk.URL_BPS_LOW), int(3600 * disk.URL_BPS_HIGH))


# ---------------------------------------------------------------------------
# The decision, with free space injectable (a one-drive CI machine must be
# able to test the two-drive failure mode)


def _assess(needs, free_by_volume, unknown=()):
    # Keyed on the drive prefix ("J:") rather than Path.parts, whose spelling
    # differs between Windows and POSIX.
    return disk.assess(
        needs,
        list(unknown),
        free_fn=lambda p: free_by_volume[str(p)[:2]],
        volume_fn=lambda p: str(p)[:2],
    )


def test_each_volume_is_checked_against_its_own_free_space():
    # Jobs on J: with plenty of room; models redirected to M: which cannot
    # hold them. Checking only the job volume and reporting "you have room"
    # while the model volume fills is the failure mode this exists for.
    needs = [
        disk.Need("rendered clips", Path("J:/jobs/x"), 100, 200),
        disk.Need("Speech recognition", Path("M:/hf"), 1_000_000, 1_000_000),
    ]
    report = _assess(needs, {"J:": 10**12, "M:": 500_000})
    assert report["action"] == "block"
    assert "M:" in report["message"]
    assert "J:" not in report["message"]


def test_unknown_free_space_warns_and_never_blocks():
    # §5.9: a volume that will not answer (network drive, permission quirk)
    # must not become a wall.
    needs = [disk.Need("rendered clips", Path("N:/jobs/x"), 10**9, 10**9)]
    report = disk.assess(
        needs, [], free_fn=lambda p: None, volume_fn=lambda p: Path(p).parts[0]
    )
    assert report["action"] == "warn"
    assert "could not be read" in report["message"]


def test_block_needs_a_confident_shortfall_and_names_both_numbers():
    needs = [disk.Need("source download", Path("C:/jobs/x"), 4_000_000_000, 18_000_000_000)]
    # Free space inside the estimate's range: the job may fit — start it,
    # warned. Blocking here would cost the user a job that could succeed.
    gray = _assess(needs, {"C:": 10_000_000_000})
    assert gray["action"] == "warn"
    # Below even the low bound: the job cannot fit. The message carries the
    # need and the free figure (the PRD's "vajag ~18 GB, brīvi 4 GB" shape).
    short = _assess(needs, {"C:": 1_000_000_000})
    assert short["action"] == "block"
    assert "18.0 GB" in short["message"]
    assert "1.0 GB" in short["message"]
    roomy = _assess(needs, {"C:": 100_000_000_000})
    assert roomy["action"] == "ok"
    assert roomy["message"] == ""


def test_unsizeable_components_are_named_not_invented():
    needs = [disk.Need("rendered clips", Path("C:/jobs/x"), 10**9, 10**9)]
    report = _assess(needs, {"C:": 0}, unknown=["ffmpeg (size depends on this machine)"])
    assert report["action"] == "block"
    assert "ffmpeg" in report["message"]


# ---------------------------------------------------------------------------
# gather(): remaining need is disk truth, and probes degrade instead of raise


def test_gather_skips_what_is_already_on_disk(monkeypatch):
    from publikclip_pipeline.ingest import normalize

    job = queue.create_job("url", "https://example.com/watch?v=x", _settings_json())
    (job.dir / "media.mp4").write_bytes(b"already downloaded")
    monkeypatch.setattr(
        normalize,
        "probe",
        lambda path: normalize.Probe(
            duration_sec=100.0, width=1920, height=1080, fps=30.0,
            vfr=False, start_time=0.0, video_codec="h264", has_audio=True,
        ),
    )
    monkeypatch.setattr(disk.setup_mod, "status", lambda s: {"items": []})

    needs, unknown = disk.gather(job, config.Settings())
    labels = [n.label for n in needs]
    # A resume after freeing space must not re-demand the media it already
    # holds — that is what makes "free up space and resume" actually work.
    assert "source download" not in labels
    assert "analysis audio" in labels
    wav = next(n for n in needs if n.label == "analysis audio")
    assert wav.low == wav.high == disk.wav_need(100.0)

    (job.dir / "audio16k.wav").write_bytes(b"wav")
    needs, _ = disk.gather(job, config.Settings())
    assert "analysis audio" not in [n.label for n in needs]


def test_gather_degrades_to_unknown_when_it_cannot_learn(monkeypatch):
    # A file job whose source cannot be probed: the check must not raise —
    # ingest owns reporting that failure properly (§5.9).
    monkeypatch.setattr(disk.setup_mod, "status", lambda s: {"items": []})
    job = queue.create_job("file", "C:/definitely/not/here.mp4", _settings_json())
    needs, unknown = disk.gather(job, config.Settings())
    assert any("source duration" in u for u in unknown)
    assert [n.label for n in needs] == ["rendered clips"]


# ---------------------------------------------------------------------------
# The queue policy: what "cannot start" means


def test_a_blocked_job_fails_with_the_numbers_and_the_queue_moves_on():
    first = queue.create_job("file", "C:/a.mp4", _settings_json())
    second = queue.create_job("file", "C:/b.mp4", _settings_json())
    # A checkpoint from an earlier run: blocking must not cost it.
    (first.dir / "ingest.json").write_text("{}", encoding="utf-8")

    message = "Not enough disk space: this job needs roughly 4.0\u201318.0 GB free on C:\\ and only 1.0 GB is free."
    disk.block_start(first, {"action": "block", "message": message})

    blocked = queue.get_job(first.id)
    # 'failed', never 'pending': next_pending() would hand a pending job
    # straight back to the shell's auto-advance, spawning it in a loop.
    assert blocked.status == "failed"
    assert blocked.error == message  # the user can tell WHY from the listing
    nxt = queue.next_pending()
    assert nxt is not None and nxt.id == second.id  # the queue is not stalled
    assert (first.dir / "ingest.json").exists()  # resume stays nearly free
