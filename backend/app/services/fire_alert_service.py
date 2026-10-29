import asyncio
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Dict, List, Optional, Tuple

from app.data_layer.crud.fire_alert_crud import FireAlertCrud
from app.data_layer.data_classes.fire_alert import FireAlert
from app.data_layer.data_classes.fire_station import NearbyFireStation
from app.data_layer.data_classes.sensor_reading import SensorReading
from app.data_layer.database_manager import DatabaseManager
from app.services.fire_verification_service import Verification
from app.services.live_events import LiveEvents
from app.telemetries.logger import logger

# Readings 5 s apart record their alerts concurrently; without this both see
# "no recent alert" and both insert. One backend process, so a local lock does.
_device_locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


def _parse_time(value: Optional[str]) -> datetime:
    return datetime.fromisoformat(value) if value else datetime.now(UTC)


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
    station, after the response has gone back to the ESP32. It is an
    incident: live until the button on the device is pressed (``resolve``).
    The ESP32 re-posts fire every 5 s; while the incident is live those
    readings belong to it, so one fire is one call.
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
        # The call happened when the alarm reading came in, not when this runs.
        alarm_at = _parse_time(reading.created_at)
        try:
            async with _device_locks[reading.device_id]:
                last = await FireAlertService._alerts_crud().latest_for_device(reading.device_id)
                # Same fire: still live, or this reading came in before the
                # button was pressed and its task ran late.
                if last is not None and (
                    last.resolved_at is None or alarm_at <= _parse_time(last.resolved_at)
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
                        "created_at": alarm_at.isoformat(),
                    }
                )
            LiveEvents.publish("alert", reading.device_id)
        except Exception as e:
            logger.error("Fire alert record failed", reading_id=reading.id, exc_info=e)

    @staticmethod
    async def live_for_device(device_id: str) -> Optional[FireAlert]:
        """The device's live incident. None on a database error: the camera
        check then runs as usual, which is the safe side."""
        try:
            return await FireAlertService._alerts_crud().live_for_device(device_id)
        except Exception as e:
            logger.error("Live incident lookup failed", device_id=device_id, exc_info=e)
            return None

    @staticmethod
    async def resolve(device_id: str) -> List[FireAlert]:
        """The button on the device was pressed: close its live incident."""
        async with _device_locks[device_id]:
            try:
                return await FireAlertService._alerts_crud().resolve_live(device_id)
            except Exception as e:
                logger.error("Incident resolve failed", device_id=device_id, exc_info=e)
                raise

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
