"""The hardware profile contract (T-10 / E1-F03 + E13-F01).

The trap pinned here: a realtime ratio measured under one hardware
configuration must never be served under another. Everything else is
arithmetic - per-stage medians summed into one ratio - and the honest
empty case: no measurements under the current key means no estimate,
not an invented one.
"""

import json

import pytest

from publikclip_pipeline import config, hardware_profile
from publikclip_pipeline.jobs import queue

GPU_SUMMARY = {
    "torch_device": "cuda",
    "gpu": "NVIDIA GeForce RTX 4070",
    "vram_gb": 12.0,
    "whisper_device": "cuda",
    "whisper_compute": "float16",
    "onnx_providers": ["CUDAExecutionProvider", "CPUExecutionProvider"],
    "cpu_threads": 16,
    "forced": None,
}

CPU_SUMMARY = {
    **GPU_SUMMARY,
    "torch_device": "cpu",
    "gpu": "",
    "whisper_device": "cpu",
    "whisper_compute": "int8",
    "onnx_providers": ["CPUExecutionProvider"],
    "forced": "cpu",
}


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("PUBLIKCLIP_HOME", str(tmp_path / "home"))
    yield


def _use_summary(monkeypatch, summary):
    monkeypatch.setattr(hardware_profile.hardware, "summary", lambda: dict(summary))


def _job_with_probe(duration_sec: float = 600.0) -> queue.Job:
    job = queue.create_job("file", "C:/nowhere/video.mp4", json.dumps(config.Settings().to_json()))
    queue.write_checkpoint(job, "ingest", 1, {"probe": {"duration_sec": duration_sec}})
    return job


def _record_stage(job_id: str, stage: str, started: float, finished: float) -> None:
    with queue._connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO stage_runs"
            " (job_id, stage, status, schema_version, started_at, finished_at)"
            " VALUES (?, ?, 'done', 1, ?, ?)",
            (job_id, stage, started, finished),
        )


def _record_full_run(job_id: str, run_started: float, stage_sec: float = 30.0) -> None:
    t = run_started
    for stage in hardware_profile.STAGES:
        _record_stage(job_id, stage, t, t + stage_sec)
        t += stage_sec


def test_cpu_threads_ignores_torchs_live_thread_setting(monkeypatch):
    """The profile key includes cpu_threads, and torch.get_num_threads() is
    ambient library state: on the reference laptop it answered 1 in one run
    and 6 in others within the same week, splitting one machine into two
    profiles and voiding the estimate (test-day F7). The count must derive
    from the machine alone."""
    import os

    import torch

    from publikclip_pipeline import hardware

    monkeypatch.setattr(torch, "get_num_threads", lambda: 1)
    assert hardware.cpu_threads() == max(1, (os.cpu_count() or 4) // 2)


def test_profile_key_splits_on_device_and_ignores_identity_fields():
    gpu_key = hardware_profile.profile_key(GPU_SUMMARY)
    assert hardware_profile.profile_key(CPU_SUMMARY) != gpu_key
    # a different compute type is a different speed - a different key
    assert (
        hardware_profile.profile_key({**GPU_SUMMARY, "whisper_compute": "int8_float16"})
        != gpu_key
    )
    # vram_gb is identity (the gpu name already names the card) and
    # `forced` is a cause, not a configuration - neither may split profiles
    assert hardware_profile.profile_key({**GPU_SUMMARY, "vram_gb": 11.9}) == gpu_key
    assert hardware_profile.profile_key({**GPU_SUMMARY, "forced": "cuda"}) == gpu_key


def test_a_measurement_under_one_key_is_never_served_under_another(monkeypatch):
    # THE trap: measure on the GPU, then force the CPU path - the GPU
    # ratio must vanish from the estimate, not keep being promised.
    _use_summary(monkeypatch, GPU_SUMMARY)
    job = _job_with_probe(600.0)
    _record_full_run(job.id, run_started=1000.0)
    profile = hardware_profile.update_after_job(job.id, run_started=1000.0)
    assert profile["estimate_ratio"] is not None

    _use_summary(monkeypatch, CPU_SUMMARY)
    profile = hardware_profile.refresh()
    assert profile["estimate_ratio"] is None
    # the GPU measurements are kept, not destroyed - they come back when
    # the GPU does
    _use_summary(monkeypatch, GPU_SUMMARY)
    assert hardware_profile.refresh()["estimate_ratio"] is not None


def test_no_estimate_until_every_stage_has_a_sample(monkeypatch):
    # a partial sum would understate silently - that is a fabricated
    # number with extra steps, so the answer is honestly None (§5.9)
    _use_summary(monkeypatch, GPU_SUMMARY)
    job = _job_with_probe(600.0)
    for stage in hardware_profile.STAGES[:-1]:  # everything but render
        _record_stage(job.id, stage, 1000.0, 1030.0)
    profile = hardware_profile.update_after_job(job.id, run_started=1000.0)
    assert profile["estimate_ratio"] is None
    assert profile["estimate_jobs"] == 1


def test_stages_cached_from_an_earlier_run_do_not_count(monkeypatch):
    # A resumed job serves early stages from checkpoints; their stage_runs
    # rows hold timings from whatever configuration ran them. Only rows
    # started inside THIS run may contribute.
    _use_summary(monkeypatch, GPU_SUMMARY)
    job = _job_with_probe(600.0)
    _record_stage(job.id, "asr", started=100.0, finished=700.0)  # an old, slow run
    _record_full_run(job.id, run_started=1000.0, stage_sec=30.0)
    profile = hardware_profile.update_after_job(job.id, run_started=1000.0)
    samples = profile["measured"][hardware_profile.profile_key(GPU_SUMMARY)]["stages"]["asr"][
        "samples"
    ]
    # one sample, from the current run (30s/600s), not the old 600s one
    assert samples == [0.05]


def test_median_and_window_survive_one_pathological_job(monkeypatch):
    _use_summary(monkeypatch, GPU_SUMMARY)
    ratios = []
    for i, stage_sec in enumerate([30.0, 30.0, 3000.0]):  # third job degenerate
        job = _job_with_probe(600.0)
        start = 1000.0 * (i + 1)
        _record_full_run(job.id, run_started=start, stage_sec=stage_sec)
        profile = hardware_profile.update_after_job(job.id, run_started=start)
        ratios.append(profile["estimate_ratio"])
    # 8 stages * 30s / 600s = 0.4 - the pathological job must not move the
    # median-based estimate
    assert ratios[-1] == pytest.approx(0.4)
    assert profile["estimate_jobs"] == 3


def test_empty_machine_says_so(monkeypatch):
    _use_summary(monkeypatch, CPU_SUMMARY)
    profile = hardware_profile.refresh()
    assert profile["estimate_ratio"] is None
    assert profile["estimate_jobs"] == 0
    assert profile["summary"]["forced"] == "cpu"
    # and the file exists for the shell to read without probing
    assert hardware_profile.profile_path().exists()
