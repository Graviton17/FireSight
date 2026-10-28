"""Route tests for fire stations, devices, and the on-fire lookup. Services are faked."""

import pytest
from fastapi.testclient import TestClient

from app.data_layer.data_classes.device import Device
from app.data_layer.data_classes.fire_station import FireStation, NearbyFireStation
from app.data_layer.data_classes.sensor_reading import SensorReading
from app.services.device_service import DeviceService
from app.services.fire_station_service import FireStationService
from app.services.fire_verification_service import FireVerificationService, Verification
from app.services.phone_location_service import PhoneLocationService
from app.services.sensor_reading_service import SensorReadingService
from main import app

NEAREST = NearbyFireStation(
    id="fs-1",
    name="Navrangpura Fire Station",
    latitude=23.036,
    longitude=72.561,
    distance_km=1.24,
    phone="101",
)
DEVICE = Device(device_id="esp32-fire-01", latitude=23.03, longitude=72.55)


@pytest.fixture
def client(monkeypatch):
    devices = {DEVICE.device_id: DEVICE}

    async def fake_get(device_id):
        return devices.get(device_id)

    async def fake_set_location(device_id, latitude, longitude, name=None, address=None):
        devices[device_id] = Device(device_id, latitude, longitude, name, address)
        return devices[device_id]

    async def fake_nearest(latitude, longitude, limit=3):
        return [NEAREST][:limit]

    async def fake_add_station(**kwargs):
        return FireStation(id="fs-new", **kwargs)

    async def fake_record_reading(**kwargs):
        return SensorReading(id="r-1", **kwargs)

    async def no_phone_fix():
        return None

    monkeypatch.setattr(DeviceService, "get", staticmethod(fake_get))
    # Never reach the real phone from config.json.
    monkeypatch.setattr(PhoneLocationService, "current_fix", staticmethod(no_phone_fix))
    monkeypatch.setattr(DeviceService, "set_location", staticmethod(fake_set_location))
    monkeypatch.setattr(FireStationService, "nearest", staticmethod(fake_nearest))
    monkeypatch.setattr(FireStationService, "add_station", staticmethod(fake_add_station))
    monkeypatch.setattr(SensorReadingService, "record_reading", staticmethod(fake_record_reading))
    return TestClient(app)


def test_nearest_by_coordinates(client):
    res = client.get("/api/v1/fire-stations/nearest", params={"latitude": 23.03, "longitude": 72.55})
    assert res.status_code == 200
    assert res.json()[0]["name"] == "Navrangpura Fire Station"
    assert res.json()[0]["distance_km"] == 1.24


def test_nearest_rejects_bad_latitude(client):
    res = client.get("/api/v1/fire-stations/nearest", params={"latitude": 123, "longitude": 72.55})
    assert res.status_code == 422


def test_add_station_manually(client):
    body = {"name": "Bopal Fire Station", "latitude": 23.03, "longitude": 72.46, "phone": "101"}
    res = client.post("/api/v1/fire-stations", json=body)
    assert res.status_code == 201
    assert res.json()["source"] == "manual"


def test_set_device_location_then_nearest(client):
    res = client.put("/api/v1/devices/esp32-fire-02", json={"latitude": 21.17, "longitude": 72.83})
    assert res.status_code == 200
    res = client.get("/api/v1/devices/esp32-fire-02/nearest-fire-stations")
    assert res.status_code == 200
    assert len(res.json()) == 1


def test_nearest_for_unknown_device_is_404(client):
    res = client.get("/api/v1/devices/nope/nearest-fire-stations")
    assert res.status_code == 404


def _reading(fire, device_id="esp32-fire-01"):
    return {"device_id": device_id, "smoke": 1800, "flame": 900, "temperature": 61.5, "fire": fire}


def test_fire_reading_returns_nearest_stations(client):
    res = client.post("/api/v1/sensor-data", json=_reading(True))
    assert res.status_code == 201
    assert res.json()["nearest_fire_stations"][0]["id"] == "fs-1"


def test_safe_reading_skips_lookup(client):
    res = client.post("/api/v1/sensor-data", json=_reading(False))
    assert res.status_code == 201
    assert res.json()["nearest_fire_stations"] == []


def test_fire_from_unlocated_device_still_stored(client):
    res = client.post("/api/v1/sensor-data", json=_reading(True, device_id="unregistered"))
    assert res.status_code == 201
    assert res.json()["nearest_fire_stations"] == []


def test_lookup_failure_does_not_fail_post(client, monkeypatch):
    async def boom(latitude, longitude, limit=3):
        raise RuntimeError("db down")

    monkeypatch.setattr(FireStationService, "nearest", staticmethod(boom))
    res = client.post("/api/v1/sensor-data", json=_reading(True))
    assert res.status_code == 201
    assert res.json()["nearest_fire_stations"] == []


def test_model_rejected_fire_returns_no_stations(client, monkeypatch):
    async def rejected(fire):
        return Verification(status="rejected", buzz=False)

    monkeypatch.setattr(FireVerificationService, "verify", staticmethod(rejected))
    res = client.post("/api/v1/sensor-data", json=_reading(True))
    assert res.status_code == 201
    assert res.json()["buzz"] is False
    assert res.json()["nearest_fire_stations"] == []
