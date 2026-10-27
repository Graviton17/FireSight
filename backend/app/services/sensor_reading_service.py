from typing import List, Optional, Tuple

from app.data_layer.crud.sensor_reading_crud import SensorReadingCrud
from app.data_layer.data_classes.sensor_reading import SensorReading
from app.data_layer.database_manager import DatabaseManager
from app.telemetries.logger import logger


class SensorReadingService:
    """Business logic for ESP32 sensor readings.

    The device decides fire / no-fire itself (all three sensors must agree and
    it debounces); the backend stores what it reports and logs alarms.
    """

    @staticmethod
    def _readings_crud() -> SensorReadingCrud:
        readings = DatabaseManager.get_instance().sensor_readings
        if readings is None:
            raise RuntimeError("SensorReading CRUD has not been initialised")
        return readings

    @staticmethod
    async def record_reading(
        device_id: str,
        smoke: int,
        flame: int,
        temperature: Optional[float],
        fire: bool,
    ) -> SensorReading:
        try:
            reading = await SensorReadingService._readings_crud().create_reading(
                device_id=device_id,
                smoke=smoke,
                flame=flame,
                temperature=temperature,
                fire=fire,
            )
        except Exception as e:
            logger.error("Error recording sensor reading", device_id=device_id, exc_info=e)
            raise

        if fire:
            logger.warning(
                "FIRE ALARM reported by device",
                device_id=device_id,
                smoke=smoke,
                flame=flame,
                temperature=temperature,
            )
        return reading

    @staticmethod
    async def get_latest(device_id: str) -> Optional[SensorReading]:
        try:
            return await SensorReadingService._readings_crud().get_latest(device_id)
        except Exception as e:
            logger.error("Error getting latest reading", device_id=device_id, exc_info=e)
            raise

    @staticmethod
    async def list_readings(
        device_id: str,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[SensorReading], int]:
        try:
            return await SensorReadingService._readings_crud().list_for_device(
                device_id, page=page, page_size=page_size
            )
        except Exception as e:
            logger.error("Error listing readings", device_id=device_id, exc_info=e)
            raise
