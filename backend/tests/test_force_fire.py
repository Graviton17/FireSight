"""detection.force_fire (testing switch) makes the model always report fire."""

import contextlib
import io
import threading
from types import SimpleNamespace

import pytest

from app.core.detection.fire_classifier import FireClassifier
from app.static_memory_cache import StaticMemoryCache


class _Tensor(list):
    def softmax(self, _dim):
        return self

    def tolist(self):
        return list(self)


def _classifier(probabilities):
    """A FireClassifier whose model returns fixed probabilities (no torch needed)."""
    clf = object.__new__(FireClassifier)
    clf._torch = SimpleNamespace(inference_mode=contextlib.nullcontext)
    clf._lock = threading.Lock()
    clf.model_id = "stub"
    clf.device = "cpu"
    clf.fire_labels = ["fire", "smoke"]
    clf.id2label = {0: "fire", 1: "normal", 2: "smoke"}
    clf.processor = lambda images, return_tensors: SimpleNamespace(to=lambda device: {})
    clf.model = lambda **_: SimpleNamespace(logits=[_Tensor(probabilities)])
    return clf


def _jpeg():
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (8, 8)).save(buffer, format="JPEG")
    return buffer.getvalue()


@pytest.fixture
def detection_config(monkeypatch):
    def set_config(**detection):
        monkeypatch.setattr(StaticMemoryCache, "config", {"detection": {"threshold": 0.7, **detection}})
        monkeypatch.setattr(StaticMemoryCache, "reload_if_changed", classmethod(lambda cls: None))

    return set_config


def test_normal_image_is_not_fire(detection_config):
    detection_config()
    prediction = _classifier([0.05, 0.9, 0.05]).predict(_jpeg())
    assert prediction.fire_detected is False


def test_force_fire_overrides_verdict_but_keeps_scores(detection_config):
    detection_config(force_fire=True)
    prediction = _classifier([0.05, 0.9, 0.05]).predict(_jpeg())
    assert prediction.fire_detected is True
    assert prediction.label == "normal"
    assert prediction.fire_score == 0.1
