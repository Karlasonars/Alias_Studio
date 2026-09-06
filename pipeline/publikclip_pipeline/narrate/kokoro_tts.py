"""The narrator: Kokoro-82M (Apache-2.0) from local weights (E20-F02).

Why Kokoro: 82M parameters, runs on a CPU at a few times realtime, the
weights and the code are Apache-2.0 with commercial use explicitly
permitted, and its voices are GENERIC — synthetic speakers with no real
person behind them, which is the line CLAUDE.md §8 draws (a synthetic
narrator is allowed; cloning a real person's voice is not). The G2P stack
underneath it (misaki, with phonemizer-fork and espeak-ng as its
out-of-dictionary fallback) is GPL-3.0-or-later, compatible with this
project's AGPL-3.0; VENDORED-LICENSES.md records the chain.

Weights come through models/registry like every other explicit download,
never through the hub's own cache: one honest download list, one
resumable fetcher, one sha256 per file (models/specs.py), and a story job
that starts on a machine without them fetches exactly what its voice
needs — the model, its config and ONE voice file — with progress on the
job's own bar. Presence is disk truth, as with every other model.

The synthesiser is an object with one method so the stage can be tested
against a fake that returns a sine (§3 forbids loading real weights in
tests); the stage never imports kokoro itself. Everything heavy is
imported inside `KokoroSynth.ensure`, so `settings story-limits` and the
deck's voice list never pay for torch.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol

import numpy as np

from ..models import registry, specs

SAMPLE_RATE = 24_000    # Kokoro's native output rate
LANG_CODE = "a"         # American English G2P; the voices below are all a/b English
REPO_ID = "hexgrad/Kokoro-82M"

#: The voices the deck offers: (id, label). All generic Kokoro speakers;
#: each has a pinned voice file in models/specs.py. Six rather than the
#: model's fifty-odd so the deck stays a row of buttons, and so every one
#: on offer is a file this build can verify.
VOICES: tuple[tuple[str, str], ...] = (
    ("af_heart", "Heart · American, warm"),
    ("af_bella", "Bella · American, bright"),
    ("am_adam", "Adam · American, low"),
    ("am_michael", "Michael · American, even"),
    ("bf_emma", "Emma · British, soft"),
    ("bm_george", "George · British, measured"),
)
DEFAULT_VOICE = "af_heart"
VOICE_IDS = tuple(vid for vid, _ in VOICES)

ProgressFn = Callable[[float, str], None]


class NarratorUnavailable(RuntimeError):
    """The narrator cannot run on this machine right now: the kokoro
    package failed to import, or its weights could not be fetched. The
    stage turns this into a described failure, never a traceback."""


class Synthesiser(Protocol):
    def synth(self, text: str, voice: str, speed: float) -> np.ndarray:
        """Mono float32 samples at SAMPLE_RATE for `text` in `voice`."""


def specs_for(voice: str) -> list[registry.ModelSpec]:
    """Everything one voice needs on disk: the model, its config, the voice."""
    if voice not in specs.KOKORO_VOICES:
        raise ValueError(f"unknown narrator voice {voice!r}; known: {list(VOICE_IDS)}")
    return [specs.KOKORO_MODEL, specs.KOKORO_CONFIG, specs.KOKORO_VOICES[voice]]


def is_present(voice: str = DEFAULT_VOICE) -> bool:
    return all(registry.is_present(s) for s in specs_for(voice))


def approx_bytes(voice: str = DEFAULT_VOICE) -> int:
    return sum(s.approx_mb * 1_000_000 for s in specs_for(voice))


def ensure_files(voice: str, progress: ProgressFn) -> list[Path]:
    """Fetch what `voice` needs (resumable, sha256-verified), returning
    the three paths. A network failure surfaces as NarratorUnavailable."""
    paths = []
    todo = specs_for(voice)
    for i, spec in enumerate(todo):
        try:
            paths.append(
                registry.ensure(spec, lambda f, m, i=i: progress((i + f) / len(todo), m))
            )
        except Exception as err:  # noqa: BLE001 - one message, whatever the transport said
            raise NarratorUnavailable(
                f"The narrator's weights could not be downloaded ({spec.filename}): {err}"
            ) from err
    return paths


class KokoroSynth:
    """The real thing. Lazy: nothing is imported or loaded until the first
    `synth`, and the pipeline is built once per process."""

    def __init__(self, device: str | None = None):
        self._device = device
        self._pipeline = None
        self._voice_paths: dict[str, Path] = {}

    def ensure(self, voice: str, progress: ProgressFn) -> None:
        model_path, config_path, voice_path = ensure_files(voice, progress)
        self._voice_paths[voice] = voice_path
        if self._pipeline is not None:
            return
        try:
            import torch
            from kokoro import KModel, KPipeline
        except Exception as err:  # noqa: BLE001 - an import failure IS the degradation
            raise NarratorUnavailable(f"The kokoro package could not be loaded: {err}") from err
        from .. import hardware

        device = self._device or hardware.torch_device()
        try:
            model = KModel(repo_id=REPO_ID, config=str(config_path), model=str(model_path))
            model = model.to(device).eval()
            with torch.no_grad():
                self._pipeline = KPipeline(
                    lang_code=LANG_CODE, repo_id=REPO_ID, model=model, device=device
                )
        except Exception as err:  # noqa: BLE001 - CUDA hiccups, a corrupt file: one message
            raise NarratorUnavailable(f"The narrator could not start: {err}") from err

    def synth(self, text: str, voice: str, speed: float) -> np.ndarray:
        if self._pipeline is None or voice not in self._voice_paths:
            self.ensure(voice, lambda f, m: None)
        import torch

        chunks: list[np.ndarray] = []
        with torch.no_grad():
            # A `.pt` path as the voice makes the pipeline load OUR file
            # instead of fetching by name from the hub (load_single_voice).
            for result in self._pipeline(
                text, voice=str(self._voice_paths[voice]), speed=float(speed), split_pattern=r"\n+"
            ):
                audio = getattr(result, "audio", None)
                if audio is None:
                    continue
                chunks.append(np.asarray(audio.detach().cpu().numpy(), dtype=np.float32).reshape(-1))
        if not chunks:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(chunks)
