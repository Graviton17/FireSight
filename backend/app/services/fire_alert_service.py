from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import List, Optional, Tuple

from app.data_layer.crud.fire_alert_crud import FireAlertCrud
from app.data_layer.data_classes.fire_alert import FireAlert
from app.data_layer.data_classes.fire_station import NearbyFireStation
from app.data_layer.data_classes.sensor_reading import SensorReading
from app.data_layer.database_manager import DatabaseManager
from app.services.fire_verification_service import Verification
from app.telemetries.logger import logger

# The ESP32 re-posts fire every 5 s while it lasts; one fire is one call.
# A device's next alarm counts as a new call only after this long.
ALERT_COOLDOWN = timedelta(minutes=5)


@dataclass
class FireAlertView:
    """An alert with the names of both ends, for the map popups."""

    alert: FireAlert
    device_name: Optional[str] = None
    station_name: Optional[str] = None
    station_phone: Optional[str] = None


class FireAlertService:
    """Which device called which fire station, and when.

    An alert is written when a reading buzzes and the device has a nearest
    station, after the response has gone back to the ESP32. Readings within
    ``ALERT_COOLDOWN`` of the device's last alert belong to the same fire.
    """

    @staticmethod
    def _alerts_crud() -> FireAlertCrud:
        alerts = DatabaseManager.get_instance().fire_alerts
        if alerts is None:
            raise RuntimeError("FireAlert CRUD has not been initialised")
        return alerts

    @staticmethod
    async def record(
        reading: SensorReading, verification: Verification, stations: List[NearbyFireStation]
    ) -> None:
        """Background task. Never raises: the alarm has already been answered."""
        if not verification.buzz or not stations:
            return
        nearest = stations[0]
        try:
            last = await FireAlertService._alerts_crud().latest_for_device(reading.device_id)
            if last is not None and last.created_at and (
                datetime.now(UTC) - datetime.fromisoformat(last.created_at) < ALERT_COOLDOWN
            ):
                return
            device = await DatabaseManager.get_instance().devices.get_by_device_id(reading.device_id)
            if device is None:
                return
            prediction = verification.prediction
            await FireAlertService._alerts_crud().create_alert(
                {
                    "reading_id": reading.id,
                    "device_id": reading.device_id,
                    "fire_station_id": nearest.id,
                    "distance_km": nearest.distance_km,
                    "device_latitude": device.latitude,
                    "device_longitude": device.longitude,
                    "verification_status": verification.status,
                    "fire_score": prediction.fire_score if prediction else None,
                    "smoke": reading.smoke,
                    "flame": reading.flame,
                    "temperature": reading.temperature,
                }
            )
        except Exception as e:
            logger.error("Fire alert record failed", reading_id=reading.id, exc_info=e)

    @staticmethod
    async def list_for_station(
        fire_station_id: str, page: int = 1, page_size: int = 20
    ) -> Tuple[List[FireAlertView], int]:
        try:
            alerts, total = await FireAlertService._alerts_crud().list_for_station(
                fire_station_id, page=page, page_size=page_size
            )
            devices = await DatabaseManager.get_instance().devices.get_by_device_ids(
                list({a.device_id for a in alerts})
            )
        except Exception as e:
            logger.error("Error listing station alerts", fire_station_id=fire_station_id, exc_info=e)
            raise
        views = [
            FireAlertView(alert=a, device_name=getattr(devices.get(a.device_id), "name", None))
            for a in alerts
        ]
        return views, total

    @staticmethod
    async def list_for_device(
        device_id: str, page: int = 1, page_size: int = 20
    ) -> Tuple[List[FireAlertView], int]:
        try:
            alerts, total = await FireAlertService._alerts_crud().list_for_device(
                device_id, page=page, page_size=page_size
            )
            stations = await DatabaseManager.get_instance().fire_stations.get_by_ids(
                list({a.fire_station_id for a in alerts})
            )
        except Exception as e:
            logger.error("Error listing device alerts", device_id=device_id, exc_info=e)
            raise
        by_id = {s.id: s for s in stations}
        views = [
            FireAlertView(
                alert=a,
                station_name=getattr(by_id.get(a.fire_station_id), "name", None),
                station_phone=getattr(by_id.get(a.fire_station_id), "phone", None),
            )
            for a in alerts
        ]
        return views, total
