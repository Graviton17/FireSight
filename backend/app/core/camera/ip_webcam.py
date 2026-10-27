"""Client for the Android "IP Webcam" app.

The app serves a snapshot over plain HTTP on the phone's LAN address:

* ``/shot.jpg``  — current video frame (fast, video resolution)
* ``/photo.jpg`` — takes a real photo with autofocus (slower, full resolution)

If "Login/password" is set in the app, it uses HTTP basic auth.
"""

from __future__ import annotations

from typing import Optional, Tuple

import httpx

from app.core.storage.constants import FireImageLimits
from app.static_memory_cache import StaticMemoryCache


class CameraError(Exception):
    """The phone could not be reached or returned something that isn't a JPEG."""


class IpWebcamClient:
    def __init__(
        self,
        base_url: str,
        snapshot_path: str = "/shot.jpg",
        timeout_seconds: float = 10.0,
        auth: Optional[Tuple[str, str]] = None,
    ):
        self.snapshot_url = f"{base_url.rstrip('/')}/{snapshot_path.lstrip('/')}"
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
