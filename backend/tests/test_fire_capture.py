"""Phone camera client, camera health check and image storage. All faked."""

import asyncio
from datetime import UTC, datetime

import httpx
import pytest

from app.core.camera import CameraError, IpWebcamClient
from app.core.storage import FireImageStorage
from app.data_layer.data_classes.fire_image import FireImage
from app.data_layer.data_classes.sensor_reading import SensorReading
from app.services import fire_capture_service
from app.services.fire_capture_service import FireCaptureService
from app.static_memory_cache import StaticMemoryCache

JPEG = b"\xff\xd8\xff\xe0fake-jpeg-body"
CAPTURED_AT = datetime(2026, 10, 29, 12, 0, 0, tzinfo=UTC)


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
    monkeypatch.setattr(StaticMemoryCache, "config", {"camera": {"base_url": "http://phone:8080"}})
    monkeypatch.setattr(StaticMemoryCache, "reload_if_changed", classmethod(lambda cls: False))


def _reading():
    return SensorReading(id="r-9", device_id="esp32-fire-01", smoke=1800, flame=900, fire=True)


def _fake_storage(monkeypatch, db):
    uploads, deletes = [], []

    async def fake_upload(self, *, object_path, file_content, **kwargs):
        uploads.append((object_path, file_content))
        return object_path

    async def fake_delete(self, object_path):
        deletes.append(object_path)
        return True

    monkeypatch.setattr(FireImageStorage, "upload", fake_upload)
    monkeypatch.setattr(FireImageStorage, "delete", fake_delete)
    monkeypatch.setattr(fire_capture_service.DatabaseManager, "get_instance", classmethod(lambda cls: db))
    return uploads, deletes


def test_store_image_uploads_and_records(monkeypatch):
    db = FakeDbManager()
    uploads, deletes = _fake_storage(monkeypatch, db)

    image = asyncio.run(FireCaptureService.store_image(_reading(), JPEG, CAPTURED_AT))

    assert image is not None
    assert image.reading_id == "r-9"
    assert image.device_id == "esp32-fire-01"
    assert image.bucket == "fire-images"
    assert image.storage_path == "esp32-fire-01/2026-10-29/r-9.jpg"
    assert image.content_type == "image/jpeg"
    assert image.size_bytes == len(JPEG)
    assert image.captured_at == CAPTURED_AT.isoformat()
    assert uploads == [(image.storage_path, JPEG)]
    assert db.fire_images.rows == [image]
    assert deletes == []


def test_failed_record_deletes_uploaded_object(monkeypatch):
    db = FakeDbManager(fail=True)
    uploads, deletes = _fake_storage(monkeypatch, db)

    assert asyncio.run(FireCaptureService.store_image(_reading(), JPEG, CAPTURED_AT)) is None
    assert deletes == [uploads[0][0]]


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
