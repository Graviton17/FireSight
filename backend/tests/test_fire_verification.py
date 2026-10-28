"""Second verification: camera + image model decide whether the ESP32 buzzes."""

import asyncio
import time
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.core.camera import CameraError, IpWebcamClient
from app.core.detection import FireClassifier, FirePrediction
from app.data_layer.data_classes.fire_image import FireImage
from app.data_layer.data_classes.sensor_reading import SensorReading
from app.services import fire_verification_service
from app.services.fire_capture_service import FireCaptureService
from app.services.fire_verification_service import FireVerificationService, Verification
from app.services.sensor_reading_service import SensorReadingService
from app.static_memory_cache import StaticMemoryCache
from main import app

JPEG = b"\xff\xd8\xff\xe0fake-jpeg-body"

FIRE_BODY = {
    "device_id": "esp32-fire-01",
    "smoke": 1800,
    "flame": 900,
    "temperature": 61.5,
    "fire": True,
}


def _prediction(fire_score):
    return FirePrediction(
        model="test/model",
        label="fire" if fire_score >= 0.5 else "normal",
        fire_score=fire_score,
        threshold=0.5,
        fire_detected=fire_score >= 0.5,
        scores={"fire": fire_score, "normal": round(1 - fire_score, 4), "smoke": 0.0},
        inference_ms=42,
    )


class FakeClassifier:
    def __init__(self, fire_score=0.9, error=None, delay=0.0):
        self.fire_score = fire_score
        self.error = error
        self.delay = delay

    def predict(self, jpeg):
        if self.delay:
            time.sleep(self.delay)
        if self.error:
            raise self.error
        return _prediction(self.fire_score)


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setattr(
        StaticMemoryCache,
        "config",
        {"camera": {"base_url": "http://phone:8080"}, "detection": {"threshold": 0.5, "timeout_seconds": 4}},
    )
    monkeypatch.setattr(StaticMemoryCache, "reload_if_changed", classmethod(lambda cls: False))

    async def fake_capture_jpeg(self):
        return JPEG

    monkeypatch.setattr(IpWebcamClient, "capture_jpeg", fake_capture_jpeg)


def _use_classifier(monkeypatch, classifier):
    monkeypatch.setattr(FireClassifier, "get", classmethod(lambda cls: classifier))


def _verify(fire=True):
    return asyncio.run(FireVerificationService.verify(fire))


# ---------------------------------------------------------------------------
# verify()
# ---------------------------------------------------------------------------


def test_no_fire_skips_verification(monkeypatch):
    _use_classifier(monkeypatch, FakeClassifier())
    v = _verify(fire=False)
    assert (v.status, v.buzz, v.image) == ("not_needed", False, None)


def test_model_confirms_fire(monkeypatch):
    _use_classifier(monkeypatch, FakeClassifier(fire_score=0.93))
    v = _verify()
    assert (v.status, v.buzz) == ("confirmed", True)
    assert v.prediction is not None and v.prediction.label == "fire"
    assert v.image == JPEG


def test_model_rejects_fire(monkeypatch):
    _use_classifier(monkeypatch, FakeClassifier(fire_score=0.1))
    v = _verify()
    assert (v.status, v.buzz) == ("rejected", False)
    assert v.image == JPEG  # still stored as evidence


def test_model_not_loaded_is_fail_safe(monkeypatch):
    _use_classifier(monkeypatch, None)
    v = _verify()
    assert (v.status, v.buzz, v.reason) == ("unavailable", True, "fire model not loaded")


def test_camera_down_is_fail_safe(monkeypatch):
    _use_classifier(monkeypatch, FakeClassifier())

    async def broken_camera(self):
        raise CameraError("phone offline")

    monkeypatch.setattr(IpWebcamClient, "capture_jpeg", broken_camera)
    v = _verify()
    assert (v.status, v.buzz, v.reason) == ("unavailable", True, "phone offline")


def test_camera_not_configured_is_fail_safe(monkeypatch):
    _use_classifier(monkeypatch, FakeClassifier())
    monkeypatch.setattr(StaticMemoryCache, "config", {})
    v = _verify()
    assert (v.status, v.buzz, v.reason) == ("unavailable", True, "camera not configured")


def test_model_error_is_fail_safe_and_keeps_image(monkeypatch):
    _use_classifier(monkeypatch, FakeClassifier(error=RuntimeError("bad tensor")))
    v = _verify()
    assert (v.status, v.buzz, v.reason) == ("unavailable", True, "fire model error")
    assert v.image == JPEG


def test_slow_model_times_out_and_is_fail_safe(monkeypatch):
    _use_classifier(monkeypatch, FakeClassifier(delay=0.5))
    monkeypatch.setattr(StaticMemoryCache, "config", {
        "camera": {"base_url": "http://phone:8080"},
        "detection": {"timeout_seconds": 0.1},
    })
    v = _verify()
    assert (v.status, v.buzz) == ("unavailable", True)
    assert "longer than 0.1s" in (v.reason or "")


# ---------------------------------------------------------------------------
# POST /sensor-data — what the ESP32 reads
# ---------------------------------------------------------------------------


@pytest.fixture
def client(monkeypatch):
    async def fake_record_reading(**kwargs):
        return SensorReading(id="r-1", created_at="2026-10-29T12:00:00+00:00", **kwargs)

    stored = []

    async def fake_store(reading, verification):
        stored.append((reading.id, verification.status))

    monkeypatch.setattr(SensorReadingService, "record_reading", staticmethod(fake_record_reading))
    monkeypatch.setattr(FireVerificationService, "store", staticmethod(fake_store))
    test_client = TestClient(app)
    test_client.stored = stored  # type: ignore[attr-defined]
    return test_client


def test_post_confirmed_fire_says_buzz(client, monkeypatch):
    _use_classifier(monkeypatch, FakeClassifier(fire_score=0.93))
    res = client.post("/api/v1/sensor-data", json=FIRE_BODY)
    assert res.status_code == 201
    body = res.json()
    assert body["buzz"] is True
    assert body["verification"]["status"] == "confirmed"
    assert body["verification"]["label"] == "fire"
    assert body["verification"]["fire_score"] == 0.93
    # Compact JSON, which is what the firmware searches for.
    assert '"buzz":true' in res.text
    assert client.stored == [("r-1", "confirmed")]


def test_post_rejected_fire_says_no_buzz(client, monkeypatch):
    _use_classifier(monkeypatch, FakeClassifier(fire_score=0.1))
    res = client.post("/api/v1/sensor-data", json=FIRE_BODY)
    assert res.json()["buzz"] is False
    assert res.json()["verification"]["status"] == "rejected"
    assert '"buzz":false' in res.text
    assert client.stored == [("r-1", "rejected")]


def test_post_without_fire_never_captures(client, monkeypatch):
    _use_classifier(monkeypatch, FakeClassifier())
    res = client.post("/api/v1/sensor-data", json={**FIRE_BODY, "fire": False})
    assert res.json()["buzz"] is False
    assert res.json()["verification"]["status"] == "not_needed"
    assert client.stored == []


# ---------------------------------------------------------------------------
# store() — image + detection rows after the response
# ---------------------------------------------------------------------------


class FakeDetections:
    def __init__(self):
        self.rows = []

    async def create_detection(self, **kwargs):
        self.rows.append(kwargs)


class FakeDbManager:
    def __init__(self):
        self.fire_detections = FakeDetections()


def _use_db(monkeypatch, db):
    monkeypatch.setattr(
        fire_verification_service.DatabaseManager, "get_instance", classmethod(lambda cls: db)
    )


def _reading():
    return SensorReading(id="r-9", device_id="esp32-fire-01", smoke=1800, flame=900, fire=True)


def test_store_writes_image_and_detection(monkeypatch):
    db = FakeDbManager()
    captured_at = datetime(2026, 10, 29, 12, 0, tzinfo=UTC)

    async def fake_store_image(reading, image, at):
        return FireImage(
            id="img-1", reading_id=reading.id, device_id=reading.device_id,
            bucket="fire-images", storage_path="p.jpg", content_type="image/jpeg",
            size_bytes=len(image), captured_at=at.isoformat(),
        )

    monkeypatch.setattr(FireCaptureService, "store_image", staticmethod(fake_store_image))
    _use_db(monkeypatch, db)

    verification = Verification(
        status="confirmed", buzz=True, prediction=_prediction(0.93), image=JPEG, captured_at=captured_at
    )
    asyncio.run(FireVerificationService.store(_reading(), verification))

    assert len(db.fire_detections.rows) == 1
    row = db.fire_detections.rows[0]
    assert row["image_id"] == "img-1"
    assert row["reading_id"] == "r-9"
    assert row["label"] == "fire"
    assert row["fire_score"] == 0.93
    assert row["fire_detected"] is True
    assert row["inference_ms"] == 42


def test_store_without_prediction_saves_image_only(monkeypatch):
    db = FakeDbManager()
    images = []

    async def fake_store_image(reading, image, at):
        images.append(reading.id)
        return None

    monkeypatch.setattr(FireCaptureService, "store_image", staticmethod(fake_store_image))
    _use_db(monkeypatch, db)

    verification = Verification(
        status="unavailable", buzz=True, reason="fire model error", image=JPEG, captured_at=datetime.now(UTC)
    )
    asyncio.run(FireVerificationService.store(_reading(), verification))
    assert images == ["r-9"]
    assert db.fire_detections.rows == []
