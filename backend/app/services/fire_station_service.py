from typing import List, Optional, Tuple

from app.data_layer.crud.fire_station_crud import FireStationCrud
from app.data_layer.data_classes.fire_station import FireStation, MapFireStation, NearbyFireStation
from app.data_layer.database_manager import DatabaseManager
from app.services.device_service import DeviceService
from app.telemetries.logger import logger


class FireStationService:
    """Fire station directory and nearest-station lookup.

    Distances are straight-line, computed in Postgres by
    ``nearest_fire_stations()`` (PostGIS, GiST-indexed). Road distance would
    need a routing API.
    """

    @staticmethod
    def _stations_crud() -> FireStationCrud:
        stations = DatabaseManager.get_instance().fire_stations
        if stations is None:
            raise RuntimeError("FireStation CRUD has not been initialised")
        return stations

    @staticmethod
    async def add_station(
        name: str,
        latitude: float,
        longitude: float,
        address: Optional[str] = None,
        city: Optional[str] = None,
        postal_code: Optional[str] = None,
        phone: Optional[str] = None,
        google_maps_url: Optional[str] = None,
    ) -> FireStation:
        try:
            return await FireStationService._stations_crud().create(
                {
                    "name": name,
                    "latitude": latitude,
                    "longitude": longitude,
                    "address": address,
                    "city": city,
                    "postal_code": postal_code,
                    "phone": phone,
                    "google_maps_url": google_maps_url,
                    "source": "manual",
                }
            )
        except Exception as e:
            logger.error("Error adding fire station", name=name, exc_info=e)
            raise

    @staticmethod
    async def list_stations(
        page: int = 1, page_size: int = 50, search: Optional[str] = None
    ) -> Tuple[List[FireStation], int]:
        try:
            return await FireStationService._stations_crud().list_stations(
                page=page, page_size=page_size, search=search
            )
        except Exception as e:
            logger.error("Error listing fire stations", exc_info=e)
            raise

    @staticmethod
    async def get(station_id: str) -> Optional[FireStation]:
        try:
            return await FireStationService._stations_crud().get_by_id(station_id)
        except Exception as e:
            logger.error("Error getting fire station", station_id=station_id, exc_info=e)
            raise

    @staticmethod
    async def in_bounds(
        min_lat: float, min_lng: float, max_lat: float, max_lng: float, limit: int = 500
    ) -> List[MapFireStation]:
        """Stations inside a map viewport, with how often each has been called."""
        try:
            return await FireStationService._stations_crud().in_bounds(
                min_lat, min_lng, max_lat, max_lng, limit
            )
        except Exception as e:
            logger.error("Error listing fire stations in bounds", exc_info=e)
            raise

    @staticmethod
    async def nearest(latitude: float, longitude: float, limit: int = 3) -> List[NearbyFireStation]:
        try:
            return await FireStationService._stations_crud().nearest(latitude, longitude, limit)
        except Exception as e:
            logger.error("Error finding nearest fire stations", exc_info=e)
            raise

    @staticmethod
    async def nearest_to_device(device_id: str, limit: int = 3) -> Optional[List[NearbyFireStation]]:
        """``None`` when the device has no location (no manual pin, no phone GPS fix)."""
        device = await DeviceService.resolve_location(device_id)
        if device is None:
            return None
        return await FireStationService.nearest(device.latitude, device.longitude, limit)

    @staticmethod
    async def nearest_for_alarm(device_id: str, limit: int = 3) -> List[NearbyFireStation]:
        """Nearest stations for a device that just reported fire.

        Never raises: the reading is already stored, and a lookup failure must
        not turn the ESP32's POST into an error.
        """
        try:
            device = await DeviceService.resolve_location(device_id)
            stations = (
                await FireStationService.nearest(device.latitude, device.longitude, limit)
                if device is not None
                else None
            )
        except Exception as e:
            logger.error("Nearest fire station lookup failed", device_id=device_id, exc_info=e)
            return []

        if device is None or stations is None:
            logger.warning(
                "FIRE ALARM but device has no location: tick 'Get location' on the IP Webcam "
                "Sensors page, or set it with PUT /api/v1/devices/{device_id}",
                device_id=device_id,
            )
            return []
        if not stations:
            logger.warning("FIRE ALARM but fire_stations table is empty", device_id=device_id)
            return []

        logger.warning(
            "Fire location",
            device_id=device_id,
            latitude=device.latitude,
            longitude=device.longitude,
            source=device.location_source,
            accuracy_m=device.location_accuracy_m,
            maps=f"https://maps.google.com/?q={device.latitude},{device.longitude}",
        )
        nearest = stations[0]
        logger.warning(
            "Nearest fire station",
            device_id=device_id,
            station=nearest.name,
            phone=nearest.phone,
            distance_km=round(nearest.distance_km, 2),
            maps=nearest.google_maps_url,
        )
        return stations
