"""Accelerator detection + performance-path tests.

The hardware layer's contract is that it can never make things worse: a
missing driver, a half-installed CUDA runtime, or an onnxruntime build
without GPU support must all degrade to the CPU path silently rather than
failing a job. These tests pin that down, plus the two settings that trade
fidelity for speed.
"""

import subprocess
import tempfile
from pathlib import Path

import pytest

from publikclip_pipeline import config, hardware
from publikclip_pipeline.candidates.stage import detect_scenes_ffmpeg
from publikclip_pipeline.render import ffmpeg_bin, renderer


@pytest.fixture(autouse=True)
def clear_caches():
    """Detection is lru_cached by design (probing is expensive); tests must
    not inherit a previous test's answer."""
    for fn in (
        hardware.cuda_available, hardware.vram_gb, hardware.gpu_name,
        hardware.ctranslate2_cuda_ok, hardware._register_nvidia_dll_dirs,
    ):
        fn.cache_clear()
    yield
    for fn in (
        hardware.cuda_available, hardware.vram_gb, hardware.gpu_name,
        hardware.ctranslate2_cuda_ok, hardware._register_nvidia_dll_dirs,
    ):
        fn.cache_clear()


# ---------------------------------------------------------------------------
# The hardware layer must never make a job fail


def test_detection_never_raises_and_returns_usable_values():
    s = hardware.summary()
    assert s["torch_device"] in ("cuda", "cpu")
    assert s["whisper_device"] in ("cuda", "cpu")
    assert s["whisper_compute"] in ("int8", "float16", "int8_float16")
    assert "CPUExecutionProvider" in s["onnx_providers"]
    assert s["cpu_threads"] >= 1


def test_env_override_forces_cpu(monkeypatch):
    """The documented escape hatch when a GPU path misbehaves."""
    monkeypatch.setenv("PUBLIKCLIP_DEVICE", "cpu")
    for fn in (hardware.cuda_available, hardware.ctranslate2_cuda_ok):
        fn.cache_clear()
    assert hardware.cuda_available() is False
    assert hardware.torch_device() == "cpu"
    assert hardware.whisper_device() == ("cpu", "int8")
    assert hardware.onnx_providers() == ["CPUExecutionProvider"]


def test_broken_torch_import_degrades_to_cpu(monkeypatch):
    """A torch that raises on import must not take the pipeline with it."""
    import builtins

    real_import = builtins.__import__

    def boom(name, *a, **kw):
        if name == "torch":
            raise ImportError("simulated broken install")
        return real_import(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", boom)
    hardware.cuda_available.cache_clear()
    assert hardware.cuda_available() is False
    assert hardware.torch_device() == "cpu"


def test_cpu_fallback_keeps_the_original_whisper_compute_type():
    """The CPU path must stay exactly what it was before GPU support —
    int8 — so nothing changes for machines without a usable GPU."""
    if hardware.ctranslate2_cuda_ok():
        pytest.skip("GPU is usable here; CPU fallback covered by the env test")
    assert hardware.whisper_device() == ("cpu", "int8")


def test_onnx_providers_always_include_cpu_last():
    """CUDA first, CPU as the fallback within the same session — never a
    GPU-only list, which would hard-fail on an unsupported op."""
    providers = hardware.onnx_providers()
    assert providers[-1] == "CPUExecutionProvider"


# ---------------------------------------------------------------------------
# Encoder selection


def test_software_encode_is_the_default_and_unchanged():
    args = renderer.video_encoder_args(hardware=False)
    # macOS keeps its VideoToolbox path; everywhere else this is the x264
    # reference that every existing render was produced with.
    assert "libx264" in args or "videotoolbox" in " ".join(args)


def test_hardware_encode_picks_an_accelerator_when_one_works():
    args = renderer.video_encoder_args(hardware=True)
    assert "-c:v" in args
    chosen = renderer.hardware_encoder_name()
    if chosen:
        assert chosen in args, "a working accelerator was found but not used"
        assert "libx264" not in args
    else:
        assert "libx264" in args, "no accelerator works, so x264 must be the fallback"


def test_listed_encoder_is_not_assumed_usable():
    """The bug this guards: h264_nvenc is compiled into every ffmpeg build and
    lists fine, but refuses to open when the driver's NVENC API is older than
    the build requires. Selecting on the listing alone produced a setting that
    failed the render instead of falling back."""
    listed = renderer._available_encoders()
    if "h264_nvenc" not in listed:
        pytest.skip("no nvenc in this ffmpeg build")
    args = renderer.video_encoder_args(hardware=True)
    if not renderer.encoder_works("h264_nvenc", dict(renderer._HW_ENCODERS)["h264_nvenc"]):
        assert "h264_nvenc" not in args, "unusable encoder must not be selected"


def test_hardware_encode_never_returns_a_broken_encoder():
    """Whatever hardware=True resolves to must actually encode — otherwise the
    setting is a render failure waiting to happen."""
    args = renderer.video_encoder_args(hardware=True)
    name = args[args.index("-c:v") + 1]
    if name == "libx264":
        return  # the honest fallback
    assert renderer.encoder_works(name, tuple(args[args.index("-c:v") + 2:]))


def test_encoder_choice_changes_the_render_fingerprint():
    """Switching encoders changes the bits, so it must invalidate the cached
    render rather than leaving old x264 files in place."""
    if not renderer.hardware_encoder_name():
        pytest.skip("no working hardware encoder on this machine")
    assert renderer.video_encoder_args(False) != renderer.video_encoder_args(True)


# ---------------------------------------------------------------------------
# Fast scene detection


@pytest.fixture(scope="module")
def cut_video():
    """12 s, three hard cuts at 3/6/9 s between solid colours."""
    d = Path(tempfile.mkdtemp(prefix="publikclip-scenetest-"))
    src = d / "cuts.mp4"
    subprocess.run(
        [
            ffmpeg_bin.ffmpeg(), "-v", "error", "-y",
            "-f", "lavfi", "-i", "color=red:s=320x180:d=3",
            "-f", "lavfi", "-i", "color=blue:s=320x180:d=3",
            "-f", "lavfi", "-i", "color=white:s=320x180:d=3",
            "-f", "lavfi", "-i", "color=black:s=320x180:d=3",
            "-filter_complex", "[0][1][2][3]concat=n=4:v=1[v]", "-map", "[v]",
            "-c:v", "libx264", "-preset", "ultrafast", "-r", "25", str(src),
        ],
        check=True, timeout=300,
    )
    return src


def test_fast_scene_detect_finds_the_real_cuts(cut_video):
    scenes = detect_scenes_ffmpeg(str(cut_video))
    assert scenes is not None, "ffmpeg scene detection failed outright"
    for expected in (3.0, 6.0, 9.0):
        assert any(abs(s - expected) < 0.3 for s in scenes), (expected, scenes)


def test_fast_scene_detect_matches_pyscenedetect_shape(cut_video):
    """Both paths must hand downstream the same thing — scene START times,
    including 0.0 — or swapping detectors would quietly change the signal."""
    from publikclip_pipeline.candidates.stage import detect_scenes

    fast = detect_scenes_ffmpeg(str(cut_video))
    slow = detect_scenes(str(cut_video))
    assert fast is not None
    assert fast[0] == 0.0 and slow[0] == 0.0
    assert abs(len(fast) - len(slow)) <= 1


def test_fast_scene_detect_returns_none_on_a_bad_file():
    """A failure must be reported as None so the caller falls back, not as
    an empty list that would silently zero the scenes channel."""
    assert detect_scenes_ffmpeg("does-not-exist.mp4") is None


def test_threshold_controls_sensitivity(cut_video):
    """A very high threshold should find fewer cuts than a low one."""
    loose = detect_scenes_ffmpeg(str(cut_video), threshold=0.05)
    strict = detect_scenes_ffmpeg(str(cut_video), threshold=0.95)
    assert loose is not None and strict is not None
    assert len(strict) <= len(loose)


def test_performance_settings_round_trip():
    s = config.Settings()
    s.performance.fast_scene_detect = False
    s.performance.hardware_encode = True
    s.performance.scene_threshold = 0.5
    back = config.Settings.from_json(s.to_json())
    assert back.performance.fast_scene_detect is False
    assert back.performance.hardware_encode is True
    assert back.performance.scene_threshold == 0.5
