"""Route tests for the map endpoints (viewport queries, alerts). Services are faked."""

import asyncio
from datetime import UTC, datetime, timedelta
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.data_layer.data_classes.device import Device, MapDevice
from app.data_layer.data_classes.fire_alert import FireAlert
from app.data_layer.data_classes.fire_station import FireStation, MapFireStation, NearbyFireStation
from app.data_layer.data_classes.sensor_reading import SensorReading
from app.data_layer.database_manager import DatabaseManager
from app.services.device_service import DeviceService
from app.services.fire_alert_service import FireAlertService, FireAlertView
from app.services.fire_station_service import FireStationService
from app.services.fire_verification_service import Verification
from main import app

STATION_ID = "6f1c1d1e-0000-4000-8000-000000000001"
STATION = MapFireStation(id=STATION_ID, name="Navrangpura Fire Station", latitude=23.036, longitude=72.561, alert_count=2)
DEVICE = MapDevice(device_id="esp32-fire-01", latitude=23.03, longitude=72.55, last_fire=True, alert_count=1)
ALERT = FireAlert(
    id="a-1",
    reading_id="r-1",
    device_id="esp32-fire-01",
    fire_station_id=STATION_ID,
    distance_km=1.24,
    device_latitude=23.03,
    device_longitude=72.55,
    verification_status="confirmed",
    smoke=3000,
    flame=200,
    temperature=61.5,
    fire_score=0.93,
    created_at="2026-10-30T10:00:00+00:00",
)


@pytest.fixture
def client(monkeypatch):
    calls = {}

    async def fake_station_bounds(min_lat, min_lng, max_lat, max_lng, limit=500):
        calls["station_bounds"] = (min_lat, min_lng, max_lat, max_lng, limit)
        return [STATION][:limit]

    async def fake_device_bounds(min_lat, min_lng, max_lat, max_lng, limit=500):
        return [DEVICE][:limit]

    async def fake_get_station(station_id):
        if station_id != STATION_ID:
            return None
        return FireStation(id=STATION_ID, name=STATION.name, latitude=STATION.latitude, longitude=STATION.longitude)

    async def fake_station_alerts(fire_station_id, page=1, page_size=20):
        return [FireAlertView(alert=ALERT, device_name="Kitchen node")], 1

    async def fake_device_alerts(device_id, page=1, page_size=20):
        return [FireAlertView(alert=ALERT, station_name=STATION.name, station_phone="101")], 1

    monkeypatch.setattr(FireStationService, "in_bounds", staticmethod(fake_station_bounds))
    monkeypatch.setattr(DeviceService, "in_bounds", staticmethod(fake_device_bounds))
    monkeypatch.setattr(FireStationService, "get", staticmethod(fake_get_station))
    monkeypatch.setattr(FireAlertService, "list_for_station", staticmethod(fake_station_alerts))
    monkeypatch.setattr(FireAlertService, "list_for_device", staticmethod(fake_device_alerts))
    test_client = TestClient(app)
    test_client.calls = calls
    return test_client


BOUNDS = {"min_lat": 22.9, "min_lng": 72.4, "max_lat": 23.2, "max_lng": 72.7}


def test_stations_in_bounds(client):
    res = client.get("/api/v1/fire-stations/in-bounds", params=BOUNDS)
    assert res.status_code == 200
    body = res.json()
    assert body["items"][0]["name"] == "Navrangpura Fire Station"
    assert body["items"][0]["alert_count"] == 2
    assert body["truncated"] is False
    assert client.calls["station_bounds"] == (22.9, 72.4, 23.2, 72.7, 500)


def test_stations_in_bounds_truncated(client):
    res = client.get("/api/v1/fire-stations/in-bounds", params={**BOUNDS, "limit": 1})
    assert res.json()["truncated"] is True


def test_in_bounds_rejects_inverted_box(client):
    res = client.get("/api/v1/fire-stations/in-bounds", params={**BOUNDS, "min_lat": 24})
    assert res.status_code == 422


def test_devices_in_bounds(client):
    res = client.get("/api/v1/devices/in-bounds", params=BOUNDS)
    assert res.status_code == 200
    assert res.json()["items"][0]["device_id"] == "esp32-fire-01"
    assert res.json()["items"][0]["last_fire"] is True


def test_get_station(client):
    assert client.get(f"/api/v1/fire-stations/{STATION_ID}").json()["name"] == STATION.name
    assert client.get("/api/v1/fire-stations/6f1c1d1e-0000-4000-8000-000000000999").status_code == 404
    assert client.get("/api/v1/fire-stations/not-a-uuid").status_code == 422


def test_station_alerts_name_the_device(client):
    res = client.get(f"/api/v1/fire-stations/{STATION_ID}/alerts")
    assert res.status_code == 200
    item = res.json()["items"][0]
    assert item["device_id"] == "esp32-fire-01"
    assert item["device_name"] == "Kitchen node"
    assert item["created_at"] == "2026-10-30T10:00:00+00:00"


def test_device_alerts_name_the_station(client):
    res = client.get("/api/v1/devices/esp32-fire-01/alerts")
    assert res.status_code == 200
    item = res.json()["items"][0]
    assert item["station_name"] == STATION.name
    assert item["station_phone"] == "101"


class _FakeAlerts:
    def __init__(self):
        self.created = []
        self.latest = None

    async def latest_for_device(self, device_id):
        await asyncio.sleep(0.01)  # a real query takes a while: room for a race
        return self.latest

    async def create_alert(self, data):
        await asyncio.sleep(0.01)
        self.created.append(data)
        self.latest = replace(ALERT, created_at=data["created_at"])


class _FakeDevices:
    async def get_by_device_id(self, device_id):
        return Device(device_id=device_id, latitude=23.03, longitude=72.55)


@pytest.fixture
def fake_db(monkeypatch):
    manager = DatabaseManager()
    manager.fire_alerts = _FakeAlerts()
    manager.devices = _FakeDevices()
    monkeypatch.setattr(DatabaseManager, "_instance", manager)
    return manager


READING = SensorReading(id="r-9", device_id="esp32-fire-01", smoke=3000, flame=200, temperature=60.0, fire=True)
STATIONS = [NearbyFireStation(id=STATION_ID, name="Navrangpura", latitude=23.036, longitude=72.561, distance_km=1.24)]


def test_record_alert_for_nearest_station(fake_db):
    verification = Verification(status="unavailable", buzz=True, reason="camera down")
    asyncio.run(FireAlertService.record(READING, verification, STATIONS))
    [row] = fake_db.fire_alerts.created
    assert row["fire_station_id"] == STATION_ID
    assert row["reading_id"] == "r-9"
    assert row["verification_status"] == "unavailable"
    assert row["fire_score"] is None
    assert row["device_latitude"] == 23.03


def test_no_alert_when_not_buzzing(fake_db):
    asyncio.run(FireAlertService.record(READING, Verification(status="rejected", buzz=False), STATIONS))
    asyncio.run(FireAlertService.record(READING, Verification(status="confirmed", buzz=True), []))
    assert fake_db.fire_alerts.created == []


def test_live_incident_is_one_call(fake_db):
    # Hours later, but nobody pressed the button: still the same fire.
    fake_db.fire_alerts.latest = replace(ALERT, created_at=(datetime.now(UTC) - timedelta(hours=3)).isoformat())
    asyncio.run(FireAlertService.record(READING, Verification(status="confirmed", buzz=True), STATIONS))
    assert fake_db.fire_alerts.created == []


def test_new_call_after_resolve(fake_db):
    resolved_at = datetime.now(UTC) - timedelta(seconds=30)
    fake_db.fire_alerts.latest = replace(
        ALERT, created_at=(resolved_at - timedelta(minutes=1)).isoformat(), resolved_at=resolved_at.isoformat()
    )
    reading = replace(READING, created_at=datetime.now(UTC).isoformat())
    asyncio.run(FireAlertService.record(reading, Verification(status="confirmed", buzz=True), STATIONS))
    assert len(fake_db.fire_alerts.created) == 1


def test_reading_before_resolve_is_not_a_new_call(fake_db):
    # A reading from before the button press whose task ran late.
    fake_db.fire_alerts.latest = replace(ALERT, resolved_at="2026-10-29T09:00:10+00:00")
    reading = replace(READING, created_at="2026-10-29T09:00:05+00:00")
    asyncio.run(FireAlertService.record(reading, Verification(status="confirmed", buzz=True), STATIONS))
    assert fake_db.fire_alerts.created == []


def test_concurrent_readings_make_one_call(fake_db):
    # Two readings of the same fire, 5 s apart, recorded at the same time.
    first = replace(READING, id="r-a", created_at="2026-10-29T09:00:00+00:00")
    second = replace(READING, id="r-b", created_at="2026-10-29T09:00:05+00:00")
    confirmed = Verification(status="confirmed", buzz=True)

    async def both():
        await asyncio.gather(
            FireAlertService.record(second, confirmed, STATIONS),
            FireAlertService.record(first, confirmed, STATIONS),
        )

    asyncio.run(both())
    assert len(fake_db.fire_alerts.created) == 1


def test_call_time_is_the_alarm_time(fake_db):
    reading = replace(READING, created_at="2026-10-29T09:00:00+00:00")
    asyncio.run(FireAlertService.record(reading, Verification(status="confirmed", buzz=True), STATIONS))
    assert fake_db.fire_alerts.created[0]["created_at"] == "2026-10-29T09:00:00+00:00"
