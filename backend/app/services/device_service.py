import math
from typing import List, Optional

from app.core.camera import PhoneLocation
from app.data_layer.crud.device_crud import DeviceCrud
from app.data_layer.data_classes.device import Device, MapDevice
from app.data_layer.database_manager import DatabaseManager
from app.services.phone_location_service import PhoneLocationService
from app.static_memory_cache import StaticMemoryCache
from app.telemetries.logger import logger

# Re-save a phone fix only when the position moves more than this, so GPS
# jitter doesn't write a row on every fire reading.
_SAVE_MIN_MOVE_M = 15.0


def _distance_m(a_lat: float, a_lng: float, b_lat: float, b_lng: float) -> float:
    lat1, lng1, lat2, lng2 = map(math.radians, (a_lat, a_lng, b_lat, b_lng))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 6371000.0 * 2 * math.asin(math.sqrt(h))


class DeviceService:
    """Where each ESP32 node is installed.

    Location comes from the IP Webcam phone's GPS (the phone sits next to the
    device), unless someone pinned it by hand, which always wins.
    """

    @staticmethod
    def _devices_crud() -> DeviceCrud:
        devices = DatabaseManager.get_instance().devices
        if devices is None:
            raise RuntimeError("Device CRUD has not been initialised")
        return devices

    @staticmethod
    async def set_location(
        device_id: str,
        latitude: float,
        longitude: float,
        name: Optional[str] = None,
        address: Optional[str] = None,
    ) -> Device:
        try:
            return await DeviceService._devices_crud().upsert_device(
                device_id,
                {
                    "latitude": latitude,
                    "longitude": longitude,
                    "name": name,
                    "address": address,
                    "location_source": "manual",
                    "location_accuracy_m": None,
                },
            )
        except Exception as e:
            logger.error("Error saving device location", device_id=device_id, exc_info=e)
            raise

    @staticmethod
    async def get(device_id: str) -> Optional[Device]:
        try:
            return await DeviceService._devices_crud().get_by_device_id(device_id)
        except Exception as e:
            logger.error("Error getting device", device_id=device_id, exc_info=e)
            raise

    @staticmethod
    async def in_bounds(
        min_lat: float, min_lng: float, max_lat: float, max_lng: float, limit: int = 500
    ) -> List[MapDevice]:
        """Devices inside a map viewport, each with its latest reading and last alert."""
        try:
            return await DeviceService._devices_crud().in_bounds(
                min_lat, min_lng, max_lat, max_lng, limit
            )
        except Exception as e:
            logger.error("Error listing devices in bounds", exc_info=e)
            raise

    @staticmethod
    def _phone_serves(device_id: str) -> bool:
        """``camera.device_id`` ties the phone to one device; unset = it serves every device."""
        configured = StaticMemoryCache.get_config("camera", "device_id")
        return not configured or configured == device_id

    @staticmethod
    async def resolve_location(device_id: str) -> Optional[Device]:
        """The device with its best known location, refreshed from the phone's GPS.

        ``None`` when the device has no manual pin and the phone has no usable fix.
        """
        device = await DeviceService.get(device_id)
        if device is not None and device.location_source == "manual":
            return device
        if not DeviceService._phone_serves(device_id):
            return device

        fix = await PhoneLocationService.current_fix()
        if fix is None:
            return device  # last saved phone fix, if any
        if device is not None and _distance_m(
            device.latitude, device.longitude, fix.latitude, fix.longitude
        ) < _SAVE_MIN_MOVE_M:
            return device
        return await DeviceService._save_phone_fix(device_id, fix)

    @staticmethod
    async def _save_phone_fix(device_id: str, fix: PhoneLocation) -> Device:
        device = await DeviceService._devices_crud().upsert_device(
            device_id,
            {
                "latitude": fix.latitude,
                "longitude": fix.longitude,
                "location_source": "phone_gps",
                "location_accuracy_m": fix.accuracy_m,
            },
        )
        logger.info(
            "Device location set from phone GPS",
            device_id=device_id,
            latitude=fix.latitude,
            longitude=fix.longitude,
            accuracy_m=round(fix.accuracy_m, 1),
            provider=fix.provider,
            maps=f"https://maps.google.com/?q={fix.latitude},{fix.longitude}",
        )
        return device
