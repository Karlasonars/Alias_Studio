"""T-38: the SER loader failed silently for the product's entire life.

Two halves are pinned here. First, the loader's failure path must come back
with its reason — the bare `return None` is what let a loader that never
once succeeded go unnoticed while every job fell back to the DSP proxy.
Second, a model that does load must be used correctly: the class labels come
from the model's own label encoder (the hardcoded order was wrong — the
encoder on disk says neu/ang/hap/sad), and the probabilities are already
softmaxed (the old `.exp()` distorted every weight).

The real loader needs a ~760 MB download, so the speechbrain boundary is
faked at `foreign_class` — the same seam the production code calls.
"""

from __future__ import annotations

import numpy as np
import torch

from publikclip_pipeline.events import ser, stage

SEGMENTS = [{"start": 0.0, "end": 10.0}]
Y16K = np.zeros(16000 * 10, dtype=np.float32)


class _FakeClassifier:
    """Stands in for CustomEncoderWav2vec2Classifier: real ind2lab shape,
    plain-softmax output (sums to 1), like the model's hparams produce."""

    def __init__(self, ind2lab: dict, probs: list[float]):
        self.hparams = type("H", (), {})()
        self.hparams.label_encoder = type("E", (), {})()
        self.hparams.label_encoder.ind2lab = ind2lab
        self._probs = probs

    def classify_batch(self, chunk):
        out_prob = torch.tensor([self._probs])
        return out_prob, None, None, None


# The order the real label_encoder.txt holds — NOT the old hardcoded one.
MODEL_IND2LAB = {0: "neu", 1: "ang", 2: "hap", 3: "sad"}


def _patch_loader(monkeypatch, fake):
    import speechbrain.inference.interfaces as sb_interfaces

    monkeypatch.setattr(sb_interfaces, "foreign_class", fake)


def test_a_load_failure_returns_its_reason_not_a_bare_none(monkeypatch):
    def boom(**kwargs):
        raise OSError(1314, "A required privilege is not held by the client")

    _patch_loader(monkeypatch, boom)
    curve, reason = ser.arousal_curve_ser(Y16K, SEGMENTS, "unused")
    assert curve is None
    assert "OSError" in reason and "1314" in reason


def test_labels_come_from_the_model_not_from_a_guess(monkeypatch):
    # One-hot on index 1, which the model says is 'ang' (weight 1.0). The
    # old code assumed index 1 was 'hap' and exponentiated the probabilities,
    # so it cannot produce 1.0 here.
    _patch_loader(
        monkeypatch,
        lambda **kwargs: _FakeClassifier(MODEL_IND2LAB, [0.0, 1.0, 0.0, 0.0]),
    )
    curve, reason = ser.arousal_curve_ser(Y16K, SEGMENTS, "unused")
    assert reason is None
    assert np.allclose(curve, ser.AROUSAL_WEIGHTS["ang"])


def test_probabilities_are_not_re_exponentiated(monkeypatch):
    # Uniform probabilities → the arousal is exactly the mean of the four
    # weights. exp() of a uniform distribution is uniform too, but no longer
    # sums to 1 — the old code returned mean * e^0.25 ≈ 0.77 here.
    _patch_loader(
        monkeypatch,
        lambda **kwargs: _FakeClassifier(MODEL_IND2LAB, [0.25, 0.25, 0.25, 0.25]),
    )
    curve, reason = ser.arousal_curve_ser(Y16K, SEGMENTS, "unused")
    assert reason is None
    expected = sum(ser.AROUSAL_WEIGHTS.values()) / len(ser.AROUSAL_WEIGHTS)
    assert np.allclose(curve, expected)


def test_a_half_loaded_label_encoder_is_refused_with_a_reason(monkeypatch):
    # The exact failure COPY_SKIP_CACHE produced while diagnosing T-38: the
    # weights load, the label encoder comes back empty, and every classify
    # would raise KeyError. A wrong curve is worse than the honest proxy.
    _patch_loader(monkeypatch, lambda **kwargs: _FakeClassifier({}, [1, 0, 0, 0]))
    curve, reason = ser.arousal_curve_ser(Y16K, SEGMENTS, "unused")
    assert curve is None
    assert "label encoder" in reason


def test_fallback_announces_itself_on_the_live_console(monkeypatch):
    monkeypatch.setattr(
        ser, "arousal_curve_ser", lambda *a, **k: (None, "OSError: [WinError 1314] …")
    )
    emitted: list[str] = []
    curves = {"dynamics": [0.1, 0.5, 0.9, 0.4], "grid_sec": 0.25}
    curve, source, reason = stage.resolve_arousal(
        Y16K, SEGMENTS, curves, lambda f, m: emitted.append(m)
    )
    assert source == "dsp-proxy"
    assert reason == "OSError: [WinError 1314] …"
    assert len(curve) > 0
    assert any("fallback" in m.lower() for m in emitted)


def test_a_working_ser_is_silent_and_labeled_ser(monkeypatch):
    monkeypatch.setattr(
        ser, "arousal_curve_ser", lambda *a, **k: (np.array([0.5, 0.6]), None)
    )
    emitted: list[str] = []
    curve, source, reason = stage.resolve_arousal(
        Y16K, SEGMENTS, {"dynamics": [], "grid_sec": 0.25}, lambda f, m: emitted.append(m)
    )
    assert source == "ser"
    assert reason is None
    assert not any("fallback" in m.lower() for m in emitted)
