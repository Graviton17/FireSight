"""Device location from the IP Webcam phone's GPS. Phone and DB are faked."""

import asyncio

import pytest

from app.core.camera import IpWebcamClient, PhoneLocation, parse_gps_json
from app.data_layer.data_classes.device import Device
from app.services.device_service import DeviceService
from app.services.phone_location_service import PhoneLocationService
from app.static_memory_cache import StaticMemoryCache

GPS_JSON = {
    "gps": {"latitude": 23.15578, "longitude": 72.66468, "altitude": 14.0, "accuracy": 11.2},
    "network": {"latitude": 23.15562, "longitude": 72.66454, "altitude": 43.9, "accuracy": 21.1},
}
FIX = PhoneLocation(latitude=23.15578, longitude=72.66468, accuracy_m=11.2, provider="gps")


def run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def camera_configured(monkeypatch):
    monkeypatch.setattr(StaticMemoryCache, "config", {"camera": {"base_url": "http://phone:8080"}})
    monkeypatch.setattr(StaticMemoryCache, "reload_if_changed", classmethod(lambda cls: False))
    PhoneLocationService.clear_cache()
    yield
    PhoneLocationService.clear_cache()


# ---------------------------------------------------------------- /gps.json parsing


def test_parse_prefers_most_accurate_provider():
    fix = parse_gps_json(GPS_JSON)
    assert fix is not None and fix.provider == "gps" and fix.accuracy_m == 11.2


def test_parse_uses_network_when_no_gps():
    fix = parse_gps_json({"network": GPS_JSON["network"]})
    assert fix is not None and fix.provider == "network"


def test_parse_empty_means_no_fix():
    # What the phone returns before "Get location" is ticked.
    assert parse_gps_json({}) is None


def test_parse_skips_malformed_provider():
    assert parse_gps_json({"gps": {"latitude": "x"}, "network": GPS_JSON["network"]}).provider == "network"


# ---------------------------------------------------------------- PhoneLocationService


def _fake_phone(monkeypatch, fix):
    calls = []

    async def fake_get_location(self, timeout_seconds):
        calls.append(timeout_seconds)
        return fix

    monkeypatch.setattr(IpWebcamClient, "get_location", fake_get_location)
    return calls


def test_inaccurate_fix_is_ignored(monkeypatch):
    _fake_phone(monkeypatch, PhoneLocation(23.1, 72.6, accuracy_m=400, provider="network"))
    assert run(PhoneLocationService.current_fix()) is None


def test_fix_is_cached(monkeypatch):
    calls = _fake_phone(monkeypatch, FIX)
    run(PhoneLocationService.current_fix())
    run(PhoneLocationService.current_fix())
    assert len(calls) == 1


def test_no_camera_configured_means_no_fix(monkeypatch):
    monkeypatch.setattr(StaticMemoryCache, "config", {})
    assert run(PhoneLocationService.current_fix()) is None


# ---------------------------------------------------------------- DeviceService.resolve_location


class FakeDevices:
    def __init__(self, existing=None):
        self.rows = {d.device_id: d for d in (existing or [])}
        self.upserts = 0

    async def get_by_device_id(self, device_id):
        return self.rows.get(device_id)

    async def upsert_device(self, device_id, data):
        self.upserts += 1
        self.rows[device_id] = Device(device_id=device_id, **data)
        return self.rows[device_id]


def _setup(monkeypatch, existing=None, fix=FIX):
    devices = FakeDevices(existing)
    monkeypatch.setattr(DeviceService, "_devices_crud", staticmethod(lambda: devices))

    async def fake_fix():
        return fix

    monkeypatch.setattr(PhoneLocationService, "current_fix", staticmethod(fake_fix))
    return devices


def test_new_device_gets_phone_location(monkeypatch):
    devices = _setup(monkeypatch)
    device = run(DeviceService.resolve_location("esp32-fire-01"))
    assert device.location_source == "phone_gps"
    assert (device.latitude, device.longitude) == (FIX.latitude, FIX.longitude)
    assert devices.upserts == 1


def test_manual_location_wins_over_phone(monkeypatch):
    manual = Device("esp32-fire-01", 23.0, 72.5, location_source="manual")
    devices = _setup(monkeypatch, [manual])
    assert run(DeviceService.resolve_location("esp32-fire-01")) is manual
    assert devices.upserts == 0


def test_gps_jitter_does_not_rewrite(monkeypatch):
    saved = Device("esp32-fire-01", FIX.latitude + 0.00005, FIX.longitude, location_source="phone_gps")
    devices = _setup(monkeypatch, [saved])  # ~5 m away
    run(DeviceService.resolve_location("esp32-fire-01"))
    assert devices.upserts == 0


def test_phone_moved_updates_location(monkeypatch):
    saved = Device("esp32-fire-01", 23.0, 72.5, location_source="phone_gps")
    devices = _setup(monkeypatch, [saved])
    device = run(DeviceService.resolve_location("esp32-fire-01"))
    assert devices.upserts == 1 and device.latitude == FIX.latitude


def test_phone_offline_keeps_last_saved_fix(monkeypatch):
    saved = Device("esp32-fire-01", 23.0, 72.5, location_source="phone_gps")
    _setup(monkeypatch, [saved], fix=None)
    assert run(DeviceService.resolve_location("esp32-fire-01")) is saved


def test_no_location_anywhere(monkeypatch):
    _setup(monkeypatch, fix=None)
    assert run(DeviceService.resolve_location("esp32-fire-01")) is None


def test_phone_tied_to_another_device(monkeypatch):
    monkeypatch.setattr(
        StaticMemoryCache, "config", {"camera": {"base_url": "http://phone:8080", "device_id": "other"}}
    )
    devices = _setup(monkeypatch)
    assert run(DeviceService.resolve_location("esp32-fire-01")) is None
    assert devices.upserts == 0


def test_manual_put_marks_source_manual(monkeypatch):
    devices = _setup(monkeypatch)
    device = run(DeviceService.set_location("esp32-fire-01", 23.0, 72.5))
    assert device.location_source == "manual"
    assert devices.rows["esp32-fire-01"].location_accuracy_m is None
