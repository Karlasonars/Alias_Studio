"""Speech-emotion arousal channel (speechbrain wav2vec2-IEMOCAP, Apache-2.0,
ungated HF weights).

Purpose in the architecture: arousal corroborates or discounts LLM shock
scores (M2: shock ×0.6 with no arousal support) and disambiguates shouting
as triumphant-vs-distressed for the music brief. It is a *supporting* signal,
so it runs sparsely — 5 s windows, 2.5 s hop, speech regions only — and the
stage falls back to a DSP arousal proxy (energy dynamics) if the model can't
load, recording which path produced the curve.

IEMOCAP's 4 classes map to arousal: angry/happy = high, neutral = mid,
sad = low. Categorical→dimensional is a blunt instrument; the curve is
consumed as a percentile signal, never as absolute emotion.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

SER_REPO = "speechbrain/emotion-recognition-wav2vec2-IEMOCAP"
WINDOW_SEC = 5.0
HOP_SEC = 2.5
GRID_SEC = 0.5  # arousal curve granularity

# Weights are keyed by label name; the order comes from the model's own label
# encoder at load time. It is neu/ang/hap/sad on disk — an assumed order
# silently weights the wrong emotions (T-38 found this hardcoded wrong).
AROUSAL_WEIGHTS = {"ang": 1.0, "hap": 0.85, "neu": 0.4, "sad": 0.15}


def _windows(segments: list[dict], duration: float) -> list[tuple[float, float]]:
    spans: list[tuple[float, float]] = []
    for seg in segments:
        start, end = float(seg["start"]), min(float(seg["end"]), duration)
        t = start
        while t < end:
            w_end = min(t + WINDOW_SEC, end)
            if w_end - t >= 1.0:
                spans.append((t, w_end))
            if w_end >= end:
                break
            t += HOP_SEC
    return spans


def arousal_curve_ser(
    y16k: np.ndarray,
    segments: list[dict],
    cache_dir: str,
    progress=None,
) -> tuple[np.ndarray | None, str | None]:
    """Arousal on a GRID_SEC grid via SER: (curve, None) on success, or
    (None, reason) when the model cannot be used. The reason must travel —
    the bare `return None` this replaces hid a loader that never once
    succeeded for the product's entire life (T-38)."""
    try:
        import torch
        from speechbrain.inference.interfaces import foreign_class
        from speechbrain.utils.fetching import LocalStrategy

        classifier = foreign_class(
            source=SER_REPO,
            pymodule_file="custom_interface.py",
            classname="CustomEncoderWav2vec2Classifier",
            savedir=cache_dir,
            run_opts={"device": "cpu"},
            # The default SYMLINK strategy needs a privilege normal Windows
            # accounts do not have — WinError 1314 killed every load ever
            # attempted. COPY is the one strategy that works unprivileged AND
            # renames label_encoder.txt -> label_encoder.ckpt itself;
            # COPY_SKIP_CACHE delegates that rename to hf_hub_download's
            # deprecated `force_filename`, which is silently ignored, so the
            # label encoder loads empty and every classify raises KeyError.
            local_strategy=LocalStrategy.COPY,
            # The repo's hyperparams put the wav2vec2-base snapshot in a
            # CWD-relative dir; keep it beside this model's other weights.
            overrides={
                "wav2vec2": {"save_path": str(Path(cache_dir) / "wav2vec2_checkpoints")}
            },
        )
    except Exception as err:  # noqa: BLE001 — degrade to DSP, but keep the reason
        return None, f"{type(err).__name__}: {err}"

    # Probe, do not trust (§5.7): a half-loaded label encoder decodes to an
    # empty or foreign label set, and a curve weighted by the wrong classes
    # would be worse than the honest DSP proxy.
    ind2lab = classifier.hparams.label_encoder.ind2lab
    labels = [ind2lab.get(i) for i in range(len(AROUSAL_WEIGHTS))]
    if sorted(str(label) for label in labels) != sorted(AROUSAL_WEIGHTS):
        return None, f"label encoder holds {labels}, expected {sorted(AROUSAL_WEIGHTS)}"

    sr = 16000
    duration = len(y16k) / sr
    n_bins = int(np.ceil(duration / GRID_SEC))
    acc = np.zeros(n_bins)
    weight = np.zeros(n_bins)
    spans = _windows(segments, duration)
    with torch.inference_mode():
        for i, (start, end) in enumerate(spans):
            chunk = torch.from_numpy(
                y16k[int(start * sr) : int(end * sr)].astype(np.float32)
            ).unsqueeze(0)
            try:
                out_prob, _, _, _ = classifier.classify_batch(chunk)
                # The Softmax in the model's hparams is plain, not log —
                # these already sum to 1, so no .exp() here.
                probs = out_prob.squeeze(0).cpu().numpy()
                arousal = float(sum(p * AROUSAL_WEIGHTS[l] for p, l in zip(probs, labels)))
            except Exception:  # noqa: BLE001 — one bad window shouldn't kill the curve
                continue
            b0, b1 = int(start / GRID_SEC), max(int(start / GRID_SEC) + 1, int(end / GRID_SEC))
            acc[b0:b1] += arousal
            weight[b0:b1] += 1.0
            if progress and i % 20 == 0:
                progress(i / max(1, len(spans)))
    curve = np.divide(acc, weight, out=np.full(n_bins, np.nan), where=weight > 0)
    # Fill non-speech bins by interpolation so consumers get a dense curve.
    if np.all(np.isnan(curve)):
        return None, "no speech window produced a classification"
    idx = np.arange(n_bins)
    good = ~np.isnan(curve)
    return np.interp(idx, idx[good], curve[good]), None


def arousal_curve_dsp(dynamics: list[float], dynamics_grid_sec: float) -> np.ndarray:
    """Fallback proxy: energy dynamics resampled onto the arousal grid and
    squashed to 0..1. Honest but blunt — the checkpoint records when this
    path was used so scoring can weight it down."""
    arr = np.asarray(dynamics, dtype=float)
    if len(arr) == 0:
        return np.zeros(0)
    factor = max(1, int(round(GRID_SEC / dynamics_grid_sec)))
    trimmed = arr[: (len(arr) // factor) * factor]
    coarse = trimmed.reshape(-1, factor).mean(axis=1) if len(trimmed) else arr
    top = np.percentile(coarse, 95) or 1.0
    return np.clip(coarse / top, 0.0, 1.0)
