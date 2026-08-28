"""First-run setup: everything a job would download, made visible up front.

E1-F01. Today the models arrive lazily, mid-job, inside whichever stage
needs them — a first-time user starts a job and waits through gigabytes of
downloads disguised as pipeline progress. This module moves that work into
a visible, resumable setup pass. The lazy path in the stages is untouched
and still works: setup is a better default, never a gate (§5.9).

What a first job actually fetches — measured 2026-08-27 from a complete
install, because the "2.5 GB" folklore had never been checked — is ~2.39 GB
spread across THREE downloaders, only one of which is ours:

  registry.ensure (ours: Range-resume, sha256-pinned, our progress):
      PANNs 327.4 MB + CAM++ 28.0 MB + vision ONNX 4.6 MB   ~360 MB  (15%)
  huggingface_hub (faster-whisper large-v3-turbo: resumes via .incomplete
      files, etag-verified, but no per-byte progress hook):  1.62 GB  (68%)
  torch.hub (wav2vec2 English alignment 377.7 MB + the silero-vad repo
      snapshot ~35 MB: NO resume, NO checksum):               413 MB  (17%)

The two foreign downloaders cannot be driven with a progress callback, so
_watched() reports the honest number instead: a thread samples the cache
directory they write into while the fetch runs (an in-process stat pass
every 0.5 s — not the T-08 subprocess-poll mistake). The fraction is real
bytes on disk over a measured total, never a bar that jumps 0 → 100.

Completion is derived from disk, never remembered. status() re-checks
files on every call, which is what makes a killed setup resume at the last
completed item for free — and the .part/.incomplete files kept by the two
resumable downloaders carry the byte offset across the kill too.

Deliberately NOT fetched here:

  - jrgillick laughter (~10 MB): OFF by default; included only when the
    user's saved settings enable laughter_specialist. Downloading a model
    the user has switched off, on their metered connection, to make a
    progress list look complete is the wrong trade.
  - speechbrain SER (~378 MB): its loader fails before the weights ever
    download (foreign_class dies after fetching one 6 KB interface file),
    so events falls back to the DSP arousal proxy — observed on every job
    on the 2026-08-27 reference machine, and recorded honestly by scoring
    in each score's `missing` list all along. Prefetching 378 MB for a
    model the loader cannot use would be pure waste; fixing the loader is
    T-38, and setup should adopt it only once it demonstrably loads.
  - non-English alignment models: the language is detected mid-transcribe
    (asr/stage.py), so only the English default is prefetched; another
    language lazily fetches its own aligner exactly as today.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import config
from .models import registry, specs

ProgressFn = Callable[[float, str], None]

# The whisper repo id mirrors faster_whisper.utils._MODELS["large-v3-turbo"]
# (pinned transitively by whisperx 3.8.6); the align filename mirrors
# torchaudio.pipelines.WAV2VEC2_ASR_BASE_960H._path (torchaudio ~=2.8.0),
# which is what whisperx resolves "en" to; the silero dir is torch.hub's
# owner_repo_ref cache naming. If an upgrade ever changes one of these, the
# item just reads "missing" and setup re-fetches — the lazy path is what
# jobs actually rely on, so drift here can cost bytes but never correctness.
_WHISPER_REPO = "mobiuslabsgmbh/faster-whisper-large-v3-turbo"
_ALIGN_EN_FILE = "wav2vec2_fairseq_base_ls960_asr_ls960.pth"
_SILERO_DIR = "snakers4_silero-vad_master"

# Display sizes + watcher denominators, measured 2026-08-27 (bytes on disk
# after a complete first run). Estimates for the UI, not contracts.
_WHISPER_BYTES = 1_621_672_079
_ALIGN_EN_BYTES = 377_664_473
_SILERO_BYTES = 35_000_000


def _hf_hub_root() -> Path:
    # Mirrors asr.stage._point_caches_at_home's setdefault: an externally
    # set HF_HOME wins there, so presence must look in the same place.
    return Path(os.environ.get("HF_HOME", str(config.models_dir() / "hf"))) / "hub"


def _torch_hub_root() -> Path:
    return Path(os.environ.get("TORCH_HOME", str(config.models_dir() / "torch"))) / "hub"


def _whisper_cache_dir() -> Path:
    return _hf_hub_root() / f"models--{_WHISPER_REPO.replace('/', '--')}"


def _whisper_present() -> bool:
    # huggingface_hub only materialises a snapshot file once its download
    # completed and verified, so existence is the completed-ness check.
    return any(_whisper_cache_dir().glob("snapshots/*/model.bin"))


def _align_en_present() -> bool:
    return (_torch_hub_root() / "checkpoints" / _ALIGN_EN_FILE).exists()


def _silero_present() -> bool:
    return (_torch_hub_root() / _SILERO_DIR).exists()


def _tree_bytes(root: Path) -> int:
    if not root.exists():
        return 0
    return sum(f.stat().st_size for f in root.rglob("*") if f.is_file())


def _watched(fetch: Callable[[], None], watch_root: Path, expected: int, progress: ProgressFn) -> None:
    """Honest progress for a downloader we do not drive: run it in a thread
    and sample the cache tree it writes into. Includes pre-existing partial
    bytes, so a resumed download shows its bar starting where the kill left
    it — which is also how the user *sees* that resume is real."""
    caught: list[Exception] = []

    def run() -> None:
        try:
            fetch()
        except Exception as err:  # noqa: BLE001 — re-raised on the main thread below
            caught.append(err)

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    while worker.is_alive():
        got = _tree_bytes(watch_root)
        if expected:
            progress(min(0.99, got / expected), f"{got / 1e6:.0f} of ~{expected / 1e6:.0f} MB")
        worker.join(0.5)
    if caught:
        raise caught[0]


def _point_caches() -> None:
    from .asr.stage import _point_caches_at_home  # the job-time code path, reused verbatim

    _point_caches_at_home()


def _fetch_whisper(progress: ProgressFn) -> None:
    _point_caches()
    from faster_whisper.utils import download_model  # noqa: PLC0415 — heavy, run-verb only

    # Exactly what whisperx.load_model triggers on first use: the same repo
    # into the same HF cache, so the job later finds it and fetches nothing.
    _watched(
        lambda: download_model("large-v3-turbo"),
        _whisper_cache_dir(),
        _WHISPER_BYTES,
        progress,
    )


def _fetch_align_en(progress: ProgressFn) -> None:
    _point_caches()
    import whisperx  # noqa: PLC0415 — heavy, run-verb only

    def go() -> None:
        # The exact call asr/stage.py makes after language detection; "en"
        # is the one default worth prefetching (see module docstring).
        model, _meta = whisperx.load_align_model(language_code="en", device="cpu")
        del model

    _watched(go, _torch_hub_root() / "checkpoints", _ALIGN_EN_BYTES, progress)


def _fetch_silero(progress: ProgressFn) -> None:
    _point_caches()
    progress(-1.0, "Fetching Silero VAD (~35 MB)…")
    import torch  # noqa: PLC0415 — heavy, run-verb only

    # Mirrors whisperx/vads/silero.py — a repo zip, so no byte fraction to
    # show; the indeterminate bar above is the honest display for it.
    torch.hub.load(
        repo_or_dir="snakers4/silero-vad", model="silero_vad", onnx=False, trust_repo=True
    )


def _fetch_ffmpeg(progress: ProgressFn) -> None:
    from .render import ffmpeg_bin

    if not ffmpeg_bin.ensure_capable(progress=progress):
        raise RuntimeError("ffmpeg with subtitle support could not be set up")


def _ffmpeg_present() -> bool:
    from .render import ffmpeg_bin

    return ffmpeg_bin.supports_captions()


@dataclass(frozen=True)
class SetupItem:
    id: str
    label: str
    bytes: int | None  # expected download size; None = depends on the machine
    present: Callable[[], bool]
    fetch: Callable[[ProgressFn], None]


def _registry_fetch(spec: registry.ModelSpec) -> Callable[[ProgressFn], None]:
    def fetch(progress: ProgressFn) -> None:
        registry.ensure(spec, progress)

    return fetch


def _vision_present() -> bool:
    return all(
        registry.is_present(s)
        for s in (specs.ULTRAFACE, specs.LR_ASD_FRONTEND, specs.LR_ASD_BACKEND)
    )


def _vision_fetch(progress: ProgressFn) -> None:
    trio = (specs.ULTRAFACE, specs.LR_ASD_FRONTEND, specs.LR_ASD_BACKEND)
    for i, spec in enumerate(trio):
        registry.ensure(spec, lambda f, m, i=i: progress((i + f) / len(trio), m))


def items(settings: "config.Settings | None" = None) -> list[SetupItem]:
    """In the order a job consumes them, so a job started mid-setup has the
    best chance its early stages find their models already on disk."""
    if settings is None:
        settings = config.load_defaults()
    out = [
        SetupItem("ffmpeg", "ffmpeg (subtitle-capable)", None, _ffmpeg_present, _fetch_ffmpeg),
        SetupItem(
            "whisper", "Speech recognition (Whisper large-v3-turbo)",
            _WHISPER_BYTES, _whisper_present, _fetch_whisper,
        ),
        SetupItem("vad", "Voice activity detection (Silero)", _SILERO_BYTES, _silero_present, _fetch_silero),
        SetupItem(
            "align-en", "Word alignment, English (wav2vec2)",
            _ALIGN_EN_BYTES, _align_en_present, _fetch_align_en,
        ),
        SetupItem(
            "campplus", "Speaker embeddings (CAM++)",
            specs.CAMPPLUS.approx_mb * 1_000_000,
            lambda: registry.is_present(specs.CAMPPLUS), _registry_fetch(specs.CAMPPLUS),
        ),
    ]
    if getattr(settings, "laughter_specialist", False):
        out.append(
            SetupItem(
                "laughter", "Laughter specialist (enabled in your settings)",
                specs.LAUGHTER.approx_mb * 1_000_000,
                lambda: registry.is_present(specs.LAUGHTER), _registry_fetch(specs.LAUGHTER),
            )
        )
    out.extend(
        [
            SetupItem(
                "panns", "Audio events (PANNs)",
                specs.PANNS_CNN14_MAX.approx_mb * 1_000_000,
                lambda: registry.is_present(specs.PANNS_CNN14_MAX),
                _registry_fetch(specs.PANNS_CNN14_MAX),
            ),
            SetupItem(
                "vision", "Face & active-speaker models",
                4_600_000, _vision_present, _vision_fetch,
            ),
        ]
    )
    return out


def status(settings: "config.Settings | None" = None) -> dict:
    """Cheap, offline, filesystem-only — safe to call on every screen entry.
    total_missing_bytes is what E1-F01 shows BEFORE any download starts."""
    listed = [
        {"id": item.id, "label": item.label, "bytes": item.bytes, "present": item.present()}
        for item in items(settings)
    ]
    return {
        "items": listed,
        "total_missing_bytes": sum(i["bytes"] or 0 for i in listed if not i["present"]),
    }


def _throttled(emit: Callable[[dict], None], item_id: str) -> ProgressFn:
    """registry.ensure reports per chunk; unthrottled that floods the JSONL
    stream and the UI behind it."""
    last = [0.0]

    def progress(fraction: float, message: str) -> None:
        now = time.monotonic()
        if now - last[0] < 0.2 and 0.0 <= fraction < 1.0:
            return
        last[0] = now
        emit(
            {
                "event": "item", "item": item_id, "state": "downloading",
                "fraction": fraction, "message": message,
            }
        )

    return progress


def run(emit: Callable[[dict], None], item_list: "list[SetupItem] | None" = None) -> dict:
    """Fetch everything missing, one item at a time, emitting JSONL events.
    A failed item is reported and skipped — one dead mirror must not hide
    the rest of the downloads (§5.9). Present items are skipped from disk
    truth, which is the whole resume story."""
    failures: list[dict] = []
    for item in item_list if item_list is not None else items():
        if item.present():
            emit({"event": "item", "item": item.id, "state": "done", "cached": True})
            continue
        emit({"event": "item", "item": item.id, "state": "downloading", "fraction": -1.0, "message": ""})
        try:
            item.fetch(_throttled(emit, item.id))
        except Exception as err:  # noqa: BLE001 — report and continue to the next item
            failures.append({"item": item.id, "error": str(err)})
            emit({"event": "item", "item": item.id, "state": "failed", "error": str(err)})
            continue
        if item.present():
            emit({"event": "item", "item": item.id, "state": "done"})
        else:
            # The fetcher returned without error but the job would still not
            # find the files (e.g. a cache env var moved mid-run). Say so
            # rather than showing a green row over a broken first job.
            message = "fetch finished but the files are not where a job will look"
            failures.append({"item": item.id, "error": message})
            emit({"event": "item", "item": item.id, "state": "failed", "error": message})
    return {"ok": not failures, "failures": failures}
