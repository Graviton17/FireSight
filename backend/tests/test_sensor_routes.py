"""Route tests for /api/v1/sensor-data. The service is faked — no database."""

import pytest
from fastapi.testclient import TestClient

from app.data_layer.data_classes.sensor_reading import SensorReading
from app.services.sensor_reading_service import SensorReadingService
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
    # No `with` block: the lifespan (and its Supabase connection) never runs.
    test_client = TestClient(app)
    test_client.stored = stored  # type: ignore[attr-defined]
    return test_client


def test_post_stores_reading(client):
    res = client.post("/api/v1/sensor-data", json=VALID_BODY)
    assert res.status_code == 201
    assert res.json()["id"] == "r-1"
    assert res.json()["fire"] is True
    assert len(client.stored) == 1


def test_post_accepts_null_temperature(client):
    body = {**VALID_BODY, "temperature": None, "fire": False}
    res = client.post("/api/v1/sensor-data", json=body)
    assert res.status_code == 201
    assert res.json()["temperature"] is None


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
