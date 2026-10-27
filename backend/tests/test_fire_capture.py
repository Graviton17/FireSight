"""Phone-camera capture on fire readings. Camera, storage and DB are faked."""

import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.camera import CameraError, IpWebcamClient
from app.core.storage import FireImageStorage
from app.data_layer.data_classes.fire_image import FireImage
from app.data_layer.data_classes.sensor_reading import SensorReading
from app.services import fire_capture_service
from app.services.fire_capture_service import FireCaptureService
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


class FakeFireImages:
    def __init__(self, fail=False):
        self.rows = []
        self.fail = fail

    async def create_image(self, **kwargs):
        if self.fail:
            raise RuntimeError("insert failed")
        image = FireImage(id="img-1", **kwargs)
        self.rows.append(image)
        return image


class FakeDbManager:
    def __init__(self, fail=False):
        self.fire_images = FakeFireImages(fail=fail)


@pytest.fixture(autouse=True)
def camera_configured(monkeypatch):
    monkeypatch.setattr(
        StaticMemoryCache,
        "config",
        {"camera": {"base_url": "http://phone:8080", "capture_interval_seconds": 10}},
    )
    monkeypatch.setattr(StaticMemoryCache, "reload_if_changed", classmethod(lambda cls: False))
    fire_capture_service._last_capture_at.clear()
    yield
    fire_capture_service._last_capture_at.clear()


@pytest.fixture
def client(monkeypatch):
    async def fake_record_reading(**kwargs):
        return SensorReading(id="r-1", created_at="2026-10-28T12:00:00+00:00", **kwargs)

    captured = []

    async def fake_capture(reading):
        captured.append(reading.id)

    monkeypatch.setattr(SensorReadingService, "record_reading", staticmethod(fake_record_reading))
    monkeypatch.setattr(FireCaptureService, "capture_for_reading", staticmethod(fake_capture))
    test_client = TestClient(app)
    test_client.captured = captured  # type: ignore[attr-defined]
    return test_client


def test_fire_post_schedules_capture(client):
    res = client.post("/api/v1/sensor-data", json=FIRE_BODY)
    assert res.status_code == 201
    assert res.json()["image_capture_scheduled"] is True
    assert client.captured == ["r-1"]


def test_safe_post_does_not_capture(client):
    res = client.post("/api/v1/sensor-data", json={**FIRE_BODY, "fire": False})
    assert res.json()["image_capture_scheduled"] is False
    assert client.captured == []


def test_cooldown_skips_repeat_fire_posts(client):
    client.post("/api/v1/sensor-data", json=FIRE_BODY)
    res = client.post("/api/v1/sensor-data", json=FIRE_BODY)
    assert res.json()["image_capture_scheduled"] is False
    assert client.captured == ["r-1"]


def test_no_camera_configured_skips_capture(client, monkeypatch):
    monkeypatch.setattr(StaticMemoryCache, "config", {})
    res = client.post("/api/v1/sensor-data", json=FIRE_BODY)
    assert res.json()["image_capture_scheduled"] is False


def _reading():
    return SensorReading(id="r-9", device_id="esp32-fire-01", smoke=1800, flame=900, fire=True)


def _fake_camera_and_storage(monkeypatch, db):
    uploads, deletes = [], []

    async def fake_capture_jpeg(self):
        return JPEG

    async def fake_upload(self, *, object_path, file_content, **kwargs):
        uploads.append((object_path, file_content))
        return object_path

    async def fake_delete(self, object_path):
        deletes.append(object_path)
        return True

    monkeypatch.setattr(IpWebcamClient, "capture_jpeg", fake_capture_jpeg)
    monkeypatch.setattr(FireImageStorage, "upload", fake_upload)
    monkeypatch.setattr(FireImageStorage, "delete", fake_delete)
    monkeypatch.setattr(fire_capture_service.DatabaseManager, "get_instance", classmethod(lambda cls: db))
    return uploads, deletes


def test_capture_uploads_and_records_image(monkeypatch):
    db = FakeDbManager()
    uploads, deletes = _fake_camera_and_storage(monkeypatch, db)

    image = asyncio.run(FireCaptureService.capture_for_reading(_reading()))

    assert image is not None
    assert image.reading_id == "r-9"
    assert image.device_id == "esp32-fire-01"
    assert image.bucket == "fire-images"
    assert image.storage_path.startswith("esp32-fire-01/") and image.storage_path.endswith("/r-9.jpg")
    assert image.content_type == "image/jpeg"
    assert image.size_bytes == len(JPEG)
    assert image.captured_at
    assert uploads == [(image.storage_path, JPEG)]
    assert db.fire_images.rows == [image]
    assert deletes == []


def test_failed_record_deletes_uploaded_object(monkeypatch):
    db = FakeDbManager(fail=True)
    uploads, deletes = _fake_camera_and_storage(monkeypatch, db)

    assert asyncio.run(FireCaptureService.capture_for_reading(_reading())) is None
    assert deletes == [uploads[0][0]]


def test_camera_failure_releases_slot(monkeypatch):
    async def broken_camera(self):
        raise CameraError("phone offline")

    monkeypatch.setattr(IpWebcamClient, "capture_jpeg", broken_camera)
    assert FireCaptureService.claim_capture_slot("esp32-fire-01") is True

    assert asyncio.run(FireCaptureService.capture_for_reading(_reading())) is None
    # Next fire reading retries instead of waiting out the cooldown.
    assert FireCaptureService.claim_capture_slot("esp32-fire-01") is True


def _client_returning(monkeypatch, response):
    real_async_client = httpx.AsyncClient

    def fake_async_client(**kwargs):
        return real_async_client(transport=httpx.MockTransport(lambda request: response), **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", fake_async_client)


def test_ip_webcam_returns_jpeg(monkeypatch):
    _client_returning(monkeypatch, httpx.Response(200, content=JPEG))
    assert asyncio.run(IpWebcamClient("http://phone:8080").capture_jpeg()) == JPEG


def test_ip_webcam_rejects_non_jpeg(monkeypatch):
    _client_returning(monkeypatch, httpx.Response(200, content=b"<html>login</html>"))
    with pytest.raises(CameraError):
        asyncio.run(IpWebcamClient("http://phone:8080").capture_jpeg())


def test_ip_webcam_rejects_http_error(monkeypatch):
    _client_returning(monkeypatch, httpx.Response(401))
    with pytest.raises(CameraError):
        asyncio.run(IpWebcamClient("http://phone:8080").capture_jpeg())


def test_latest_includes_linked_image(monkeypatch):
    reading = _reading()
    image = FireImage(
        id="img-1",
        reading_id="r-9",
        device_id="esp32-fire-01",
        bucket="fire-images",
        storage_path="esp32-fire-01/2026-10-28/r-9.jpg",
        content_type="image/jpeg",
        size_bytes=1234,
        captured_at="2026-10-28T12:00:01+00:00",
    )

    async def fake_latest(device_id):
        return reading

    async def fake_images(reading_ids):
        return {"r-9": image} if "r-9" in reading_ids else {}

    async def fake_signed_url(img):
        return "https://signed.example/" + img.storage_path

    monkeypatch.setattr(SensorReadingService, "get_latest", staticmethod(fake_latest))
    monkeypatch.setattr(FireCaptureService, "get_images_for_readings", staticmethod(fake_images))
    monkeypatch.setattr(FireCaptureService, "signed_url", staticmethod(fake_signed_url))

    res = TestClient(app).get("/api/v1/sensor-data/esp32-fire-01/latest")
    assert res.status_code == 200
    body = res.json()
    assert body["image"]["id"] == "img-1"
    assert body["image"]["reading_id"] == "r-9"
    assert body["image"]["url"] == "https://signed.example/esp32-fire-01/2026-10-28/r-9.jpg"


def test_check_camera_ok(monkeypatch):
    async def fake_capture_jpeg(self):
        return JPEG

    monkeypatch.setattr(IpWebcamClient, "capture_jpeg", fake_capture_jpeg)
    assert asyncio.run(FireCaptureService.check_camera()) is True


def test_check_camera_unreachable(monkeypatch):
    async def broken_camera(self):
        raise CameraError("phone offline")

    monkeypatch.setattr(IpWebcamClient, "capture_jpeg", broken_camera)
    assert asyncio.run(FireCaptureService.check_camera()) is False


def test_check_camera_not_configured(monkeypatch):
    monkeypatch.setattr(StaticMemoryCache, "config", {})
    assert asyncio.run(FireCaptureService.check_camera()) is False
