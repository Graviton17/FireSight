"""Client for the Android "IP Webcam" app.

The app serves a snapshot over plain HTTP on the phone's LAN address:

* ``/shot.jpg``  — current video frame (fast, video resolution)
* ``/photo.jpg`` — takes a real photo with autofocus (slower, full resolution)
* ``/gps.json``  — the phone's position, once "Get location" is ticked on the
  app's Sensors page (``/sensors.html``); ``{}`` until then

If "Login/password" is set in the app, it uses HTTP basic auth.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import httpx

from app.core.storage.constants import FireImageLimits
from app.static_memory_cache import StaticMemoryCache


class CameraError(Exception):
    """The phone could not be reached or returned something that isn't a JPEG."""


@dataclass
class PhoneLocation:
    """One position fix reported by the phone."""

    latitude: float
    longitude: float
    accuracy_m: float
    provider: str  # 'gps' (satellite) or 'network' (Wi-Fi / cell towers)


def parse_gps_json(data: Dict[str, Any]) -> Optional[PhoneLocation]:
    """Pick the most accurate provider from a ``/gps.json`` body; ``None`` if it has no fix.

    Body shape: ``{"gps": {"latitude", "longitude", "altitude", "accuracy"},
    "network": {...}}`` — either key may be missing.
    """
    fixes = []
    for provider in ("gps", "network"):
        fix = data.get(provider)
        if not isinstance(fix, dict):
            continue
        try:
            fixes.append(
                PhoneLocation(
                    latitude=float(fix["latitude"]),
                    longitude=float(fix["longitude"]),
                    accuracy_m=float(fix["accuracy"]),
                    provider=provider,
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return min(fixes, key=lambda f: f.accuracy_m) if fixes else None


class IpWebcamClient:
    def __init__(
        self,
        base_url: str,
        snapshot_path: str = "/shot.jpg",
        timeout_seconds: float = 10.0,
        auth: Optional[Tuple[str, str]] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.snapshot_url = f"{self.base_url}/{snapshot_path.lstrip('/')}"
        self.timeout_seconds = timeout_seconds
        self.auth = auth

    @classmethod
    def from_config(cls) -> Optional["IpWebcamClient"]:
        """Build from config.json ``camera``; ``None`` when no camera is configured."""
        base_url = StaticMemoryCache.get_camera_base_url()
        if not base_url:
            return None
        username = StaticMemoryCache.get_config("camera", "username")
        password = StaticMemoryCache.get_config("camera", "password")
        return cls(
            base_url=base_url,
            snapshot_path=StaticMemoryCache.get_config("camera", "snapshot_path") or "/shot.jpg",
            timeout_seconds=float(StaticMemoryCache.get_config("camera", "timeout_seconds") or 10),
            auth=(username, password) if username else None,
        )

    async def capture_jpeg(self) -> bytes:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds, auth=self.auth) as client:
                response = await client.get(self.snapshot_url)
        except httpx.HTTPError as e:
            raise CameraError(f"Camera unreachable at {self.snapshot_url}: {e}") from e

        if response.status_code != 200:
            raise CameraError(f"Camera returned HTTP {response.status_code}")
        body = response.content
        # JPEG files start with FF D8.
        if not body.startswith(b"\xff\xd8"):
            raise CameraError("Camera response is not a JPEG image")
        if len(body) > FireImageLimits.MAX_BYTES:
            raise CameraError(f"Image is {len(body)} bytes, over the {FireImageLimits.MAX_BYTES} limit")
        return body

    async def get_location(self, timeout_seconds: float) -> Optional[PhoneLocation]:
        """The phone's current position, or ``None`` when it has no fix yet."""
        url = f"{self.base_url}/gps.json"
        try:
            async with httpx.AsyncClient(timeout=timeout_seconds, auth=self.auth) as client:
                response = await client.get(url)
        except httpx.HTTPError as e:
            raise CameraError(f"Phone unreachable at {url}: {e}") from e

        if response.status_code != 200:
            raise CameraError(f"Phone returned HTTP {response.status_code} for {url}")
        try:
            data = response.json()
        except ValueError as e:
            raise CameraError("Phone /gps.json is not JSON") from e
        return parse_gps_json(data) if isinstance(data, dict) else None
