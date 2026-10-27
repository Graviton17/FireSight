"""config.json hot-reload, so the phone camera IP can change without a restart."""

import json
import os

import pytest

from app.core.camera import IpWebcamClient
from app.static_memory_cache import StaticMemoryCache


def _write(path, camera, mtime):
    path.write_text(json.dumps({"camera": camera}))
    # Force a distinct mtime; some filesystems have coarse timestamps.
    os.utime(path, (mtime, mtime))


@pytest.fixture
def config_file(tmp_path, monkeypatch):
    monkeypatch.delenv("FIRESIGHT_CAMERA_URL", raising=False)
    # Restore the real config after the test.
    monkeypatch.setattr(StaticMemoryCache, "config", StaticMemoryCache.config)
    monkeypatch.setattr(StaticMemoryCache, "_config_file", StaticMemoryCache._config_file)
    monkeypatch.setattr(StaticMemoryCache, "_config_mtime", StaticMemoryCache._config_mtime)

    path = tmp_path / "config.json"
    _write(path, {"base_url": "http://192.168.1.50:8080"}, 1_000_000)
    StaticMemoryCache.initialize(str(path))
    return path


def test_camera_url_change_is_picked_up(config_file):
    assert StaticMemoryCache.get_camera_base_url() == "http://192.168.1.50:8080"

    _write(config_file, {"base_url": "http://192.168.1.77:8080", "snapshot_path": "/photo.jpg"}, 1_000_010)

    client = IpWebcamClient.from_config()
    assert client is not None
    assert client.snapshot_url == "http://192.168.1.77:8080/photo.jpg"


def test_invalid_json_keeps_previous_config(config_file):
    config_file.write_text('{"camera": {"base_url": "http://192.168.1.')  # half-saved
    os.utime(config_file, (1_000_010, 1_000_010))

    assert StaticMemoryCache.get_camera_base_url() == "http://192.168.1.50:8080"

    _write(config_file, {"base_url": "http://192.168.1.77:8080"}, 1_000_020)
    assert StaticMemoryCache.get_camera_base_url() == "http://192.168.1.77:8080"


def test_removing_camera_section_disables_capture(config_file):
    _write(config_file, {}, 1_000_010)
    assert StaticMemoryCache.get_camera_base_url() is None
    assert IpWebcamClient.from_config() is None
