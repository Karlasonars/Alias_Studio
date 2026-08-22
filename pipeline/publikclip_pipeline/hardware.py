"""Accelerator detection.

Every model in the pipeline used to hardcode `device = "cpu"` — a decision
inherited from the macOS build, where ctranslate2 has no Metal backend. On a
machine with an NVIDIA GPU that costs an order of magnitude: an 81-minute
source measured 68.5 minutes in ASR alone at a 1.18x realtime factor.

This module answers "what should this model run on" in one place, with two
non-negotiable properties:

  1. **It never raises.** A broken driver, a half-installed CUDA runtime, or
     a GPU that is busy must degrade to CPU, not fail the job. Every probe is
     wrapped and every failure is remembered as "no".
  2. **It probes what it actually needs.** GPU presence is not the same as
     GPU usability: ctranslate2 will happily construct a CUDA model and only
     fail later, inside inference, with `cublas64_12.dll is not found`. So
     the CUDA check for ctranslate2 loads the libraries it will need up
     front rather than trusting a device count.

Set PUBLIKCLIP_DEVICE=cpu to force everything back to the CPU path — the
first thing to try when diagnosing a suspected GPU problem.
"""

from __future__ import annotations

import ctypes
import functools
import os

# large-v3-turbo is ~1.6 GB in float16, so a 4 GB card has real headroom
# even with a desktop on the same GPU — measured working on an RTX 3050 Ti
# Laptop (4 GB) at 17.1x realtime. Below this we drop to int8_float16, which
# measured 16.1x: barely slower, noticeably less memory, and the right trade
# when there isn't room to be sure.
_FLOAT16_VRAM_GB = 3.5


def _forced() -> str | None:
    value = os.environ.get("PUBLIKCLIP_DEVICE", "").strip().lower()
    return value if value in ("cpu", "cuda") else None


@functools.lru_cache(maxsize=1)
def cuda_available() -> bool:
    """Is there a usable CUDA device for torch?"""
    if _forced() == "cpu":
        return False
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:  # noqa: BLE001 — a broken install must mean "no", not a crash
        return False


@functools.lru_cache(maxsize=1)
def vram_gb() -> float:
    """Total VRAM in GB, 0.0 when unknown.

    Deliberately does NOT require CUDA torch: ctranslate2 can use the GPU
    through its own runtime while torch is still a CPU-only build, and in
    that state a torch-based probe reports 0 and would push whisper onto a
    needlessly conservative compute type. Falls back to nvidia-smi, which
    is present whenever the driver is.
    """
    try:
        import torch

        if torch.cuda.is_available():
            return torch.cuda.get_device_properties(0).total_memory / 1e9
    except Exception:  # noqa: BLE001
        pass
    return _vram_from_smi()


@functools.lru_cache(maxsize=1)
def _vram_from_smi() -> float:
    import subprocess

    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=20,
        )
        first = out.stdout.strip().splitlines()[0]
        return float(first) / 1024.0  # MiB → GB, close enough for a threshold
    except Exception:  # noqa: BLE001
        return 0.0


@functools.lru_cache(maxsize=1)
def gpu_name() -> str:
    if not cuda_available():
        return ""
    try:
        import torch

        return str(torch.cuda.get_device_name(0))
    except Exception:  # noqa: BLE001
        return ""


@functools.lru_cache(maxsize=1)
def ctranslate2_cuda_ok() -> bool:
    """Whether faster-whisper/ctranslate2 can actually run on the GPU.

    Deliberately stricter than a device count: ctranslate2 reports a CUDA
    device whenever the driver is present, but inference needs cuBLAS and
    cuDNN, which ship separately (pip `nvidia-cublas-cu12` / `nvidia-cudnn-cu12`
    or the CUDA toolkit). Constructing the model succeeds without them and
    the failure only lands mid-transcription, so probe the libraries here.
    """
    if _forced() == "cpu":
        return False
    try:
        import ctranslate2

        if ctranslate2.get_cuda_device_count() < 1:
            return False
    except Exception:  # noqa: BLE001
        return False

    # The pip wheels put their DLLs in nvidia/*/bin; make them findable
    # before probing, exactly as ctranslate2 will need them at runtime.
    _register_nvidia_dll_dirs()
    for names in (
        ("cublas64_12.dll", "libcublas.so.12"),
        ("cudnn64_9.dll", "cudnn64_8.dll", "libcudnn.so.9", "libcudnn.so.8"),
    ):
        if not any(_can_load(n) for n in names):
            return False
    return True


def _can_load(lib: str) -> bool:
    try:
        ctypes.CDLL(lib)
        return True
    except OSError:
        return False


@functools.lru_cache(maxsize=1)
def _register_nvidia_dll_dirs() -> None:
    """The nvidia-* pip wheels drop their DLLs inside site-packages rather
    than on PATH; on Windows they are invisible to ctypes/ctranslate2 until
    the directory is registered."""
    try:
        import site
        from pathlib import Path

        roots = [Path(p) for p in site.getsitepackages()]
        for root in roots:
            nvidia = root / "nvidia"
            if not nvidia.is_dir():
                continue
            for binder in nvidia.glob("*/bin"):
                if os.name == "nt":
                    try:
                        os.add_dll_directory(str(binder))
                    except (OSError, AttributeError):
                        pass
                os.environ["PATH"] = str(binder) + os.pathsep + os.environ.get("PATH", "")
    except Exception:  # noqa: BLE001 — best effort only
        pass


def torch_device() -> str:
    """'cuda' or 'cpu' for torch models (alignment, PANNs, CAM++)."""
    return "cuda" if cuda_available() else "cpu"


def whisper_device() -> tuple[str, str]:
    """(device, compute_type) for faster-whisper/ctranslate2.

    float16 on a GPU is both faster AND more accurate than the int8 CPU path
    it replaces; int8_float16 is the fallback when VRAM is tight, trading a
    little accuracy for headroom rather than risking an OOM.
    """
    if not ctranslate2_cuda_ok():
        return "cpu", "int8"
    return ("cuda", "float16" if vram_gb() >= _FLOAT16_VRAM_GB else "int8_float16")


def onnx_providers() -> list[str]:
    """Execution providers for onnxruntime (face detection, active-speaker).

    CUDA is only offered when onnxruntime-gpu is installed; the plain
    onnxruntime wheel silently ignores an unavailable provider, so ask it
    what it actually has instead of asserting.
    """
    if _forced() == "cpu" or not cuda_available():
        return ["CPUExecutionProvider"]
    try:
        import onnxruntime as ort

        if "CUDAExecutionProvider" in ort.get_available_providers():
            return ["CUDAExecutionProvider", "CPUExecutionProvider"]
    except Exception:  # noqa: BLE001
        pass
    return ["CPUExecutionProvider"]


def cpu_threads() -> int:
    """Worker threads for CPU inference. ctranslate2's default is
    conservative; matching the physical core count is a free win on the CPU
    path and harmless on the GPU one."""
    try:
        import torch

        return max(1, int(torch.get_num_threads()))
    except Exception:  # noqa: BLE001
        return max(1, (os.cpu_count() or 4) // 2)


def summary() -> dict:
    """What the pipeline decided, for the run log and the settings panel —
    a user seeing a slow run should be able to tell whether the GPU was
    used without reading source."""
    device = torch_device()
    whisper_dev, whisper_compute = whisper_device()
    return {
        "torch_device": device,
        "gpu": gpu_name(),
        "vram_gb": round(vram_gb(), 1) if vram_gb() else 0,
        "whisper_device": whisper_dev,
        "whisper_compute": whisper_compute,
        "onnx_providers": onnx_providers(),
        "cpu_threads": cpu_threads(),
        "forced": _forced(),
    }
