from typing import Optional

from app.data_layer.crud.device_crud import DeviceCrud
from app.data_layer.data_classes.device import Device
from app.data_layer.database_manager import DatabaseManager
from app.telemetries.logger import logger


class DeviceService:
    """Where each ESP32 node is installed."""

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
                {"latitude": latitude, "longitude": longitude, "name": name, "address": address},
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
