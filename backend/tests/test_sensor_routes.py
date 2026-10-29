"""Route tests for /api/v1/sensor-data. The service is faked — no database."""

import pytest
from fastapi.testclient import TestClient

from app.core.detection import FireClassifier
from app.data_layer.data_classes.sensor_reading import SensorReading
from app.services.fire_alert_service import FireAlertService
from app.services.fire_verification_service import FireVerificationService
from app.services.sensor_reading_service import SensorReadingService
from app.static_memory_cache import StaticMemoryCache
from main import app

VALID_BODY = {
    "device_id": "esp32-fire-01",
    "smoke": 1800,
    "flame": 900,
    "temperature": 61.5,
    "fire": True,
}


@pytest.fixture
def client(monkeypatch):
    stored = []

    async def fake_record_reading(**kwargs):
        reading = SensorReading(id="r-1", created_at="2026-10-27T12:00:00+00:00", **kwargs)
        stored.append(reading)
        return reading

    monkeypatch.setattr(SensorReadingService, "record_reading", staticmethod(fake_record_reading))
    # Never touch the real phone camera from config.json.
    monkeypatch.setattr(StaticMemoryCache, "config", {})
    monkeypatch.setattr(StaticMemoryCache, "reload_if_changed", classmethod(lambda cls: False))
    # No model: fire posts get the fail-safe answer without touching a camera.
    monkeypatch.setattr(FireClassifier, "get", classmethod(lambda cls: None))
    live = {}

    async def fake_live_for_device(device_id):
        return live.get(device_id)

    monkeypatch.setattr(FireAlertService, "live_for_device", staticmethod(fake_live_for_device))
    # No `with` block: the lifespan (and its Supabase connection) never runs.
    test_client = TestClient(app)
    test_client.stored = stored  # type: ignore[attr-defined]
    test_client.live = live  # type: ignore[attr-defined]
    return test_client


def test_post_stores_reading(client):
    res = client.post("/api/v1/sensor-data", json=VALID_BODY)
    assert res.status_code == 201
    assert res.json()["id"] == "r-1"
    assert res.json()["fire"] is True
    assert res.json()["buzz"] is True
    assert res.json()["verification"]["status"] == "unavailable"
    assert len(client.stored) == 1


def test_post_accepts_null_temperature(client):
    body = {**VALID_BODY, "temperature": None, "fire": False}
    res = client.post("/api/v1/sensor-data", json=body)
    assert res.status_code == 201
    assert res.json()["temperature"] is None
    assert res.json()["buzz"] is False
    assert res.json()["verification"]["status"] == "not_needed"


def test_post_rejects_out_of_range_adc(client):
    body = {**VALID_BODY, "smoke": 5000}
    res = client.post("/api/v1/sensor-data", json=body)
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "validation_error"
    assert client.stored == []


def test_post_rejects_missing_field(client):
    body = {k: v for k, v in VALID_BODY.items() if k != "fire"}
    res = client.post("/api/v1/sensor-data", json=body)
    assert res.status_code == 422


def test_live_incident_skips_the_camera(client, monkeypatch):
    async def no_camera(fire):
        raise AssertionError("camera used during a live incident")

    monkeypatch.setattr(FireVerificationService, "verify", staticmethod(no_camera))
    client.live["esp32-fire-01"] = object()
    res = client.post("/api/v1/sensor-data", json=VALID_BODY)
    assert res.status_code == 201
    assert res.json()["buzz"] is True
    assert res.json()["verification"]["status"] == "incident_live"


def test_resolve_closes_the_incident(client, monkeypatch):
    calls = []

    async def fake_resolve(device_id):
        calls.append(device_id)
        return [object()]

    monkeypatch.setattr(FireAlertService, "resolve", staticmethod(fake_resolve))
    res = client.post("/api/v1/sensor-data/esp32-fire-01/resolve")
    assert res.status_code == 200
    assert res.json() == {"resolved": 1}
    assert calls == ["esp32-fire-01"]
