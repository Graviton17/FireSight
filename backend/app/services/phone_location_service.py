import time
from typing import Optional, Tuple

from app.core.camera import CameraError, IpWebcamClient, PhoneLocation
from app.static_memory_cache import StaticMemoryCache
from app.telemetries.logger import logger

# (time.monotonic(), fix or None). A failed read is cached too, so an offline
# phone costs one timeout per TTL instead of one per fire reading.
_cached: Optional[Tuple[float, Optional[PhoneLocation]]] = None


class PhoneLocationService:
    """The IP Webcam phone's GPS position, used as the device's location.

    The phone sits next to the ESP32, so its fix is where the fire is. Called
    inline on fire readings, so reads use a short timeout and are cached for
    ``camera.location_cache_seconds``.
    """

    @staticmethod
    def _max_accuracy_m() -> float:
        return float(StaticMemoryCache.get_config("camera", "location_max_accuracy_m") or 50)

    @staticmethod
    def _timeout_seconds() -> float:
        return float(StaticMemoryCache.get_config("camera", "location_timeout_seconds") or 1.5)

    @staticmethod
    def _cache_seconds() -> float:
        return float(StaticMemoryCache.get_config("camera", "location_cache_seconds") or 60)

    @staticmethod
    def clear_cache() -> None:
        global _cached
        _cached = None

    @staticmethod
    async def current_fix() -> Optional[PhoneLocation]:
        """A fix good enough to use, or ``None`` (no camera, phone offline, no fix, too inaccurate)."""
        global _cached
        now = time.monotonic()
        if _cached is not None and now - _cached[0] < PhoneLocationService._cache_seconds():
            return _cached[1]

        fix = await PhoneLocationService._read_fix()
        _cached = (now, fix)
        return fix

    @staticmethod
    async def _read_fix() -> Optional[PhoneLocation]:
        camera = IpWebcamClient.from_config()
        if camera is None:
            return None

        try:
            fix = await camera.get_location(PhoneLocationService._timeout_seconds())
        except CameraError as e:
            logger.warning("Phone GPS read failed", error=str(e))
            return None

        if fix is None:
            logger.warning(
                "Phone has no location: tick 'Get location' on the IP Webcam Sensors page",
                url=f"{camera.base_url}/sensors.html",
            )
            return None

        max_accuracy = PhoneLocationService._max_accuracy_m()
        if fix.accuracy_m > max_accuracy:
            logger.warning(
                "Phone location too inaccurate, ignoring",
                provider=fix.provider,
                accuracy_m=round(fix.accuracy_m, 1),
                max_accuracy_m=max_accuracy,
            )
            return None
        return fix

    @staticmethod
    async def check() -> Optional[PhoneLocation]:
        """Log the phone's location at startup (like the camera check)."""
        PhoneLocationService.clear_cache()
        fix = await PhoneLocationService.current_fix()
        if fix is not None:
            logger.info(
                "Phone location OK",
                latitude=fix.latitude,
                longitude=fix.longitude,
                accuracy_m=round(fix.accuracy_m, 1),
                provider=fix.provider,
                maps=f"https://maps.google.com/?q={fix.latitude},{fix.longitude}",
            )
        return fix
