from dataclasses import asdict
from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel

from app.data_layer.data_classes.device import MapDevice
from app.data_layer.data_classes.fire_station import MapFireStation
from app.services.fire_alert_service import FireAlertView

T = TypeVar("T")


class BoundsResponse(BaseModel, Generic[T]):
    """Everything inside a map viewport, up to ``limit``."""

    items: List[T]
    # True when the limit was hit: zoom in to see the rest.
    truncated: bool


class MapFireStationResponse(BaseModel):
    id: str
    name: str
    latitude: float
    longitude: float
    alert_count: int = 0
    last_alert_at: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    phone: Optional[str] = None
    google_maps_url: Optional[str] = None


class MapDeviceResponse(BaseModel):
    device_id: str
    latitude: float
    longitude: float
    name: Optional[str] = None
    address: Optional[str] = None
    location_source: str = "manual"
    location_accuracy_m: Optional[float] = None
    last_reading_at: Optional[str] = None
    last_fire: Optional[bool] = None
    last_smoke: Optional[int] = None
    last_flame: Optional[int] = None
    last_temperature: Optional[float] = None
    last_alert_at: Optional[str] = None
    alert_count: int = 0


class FireAlertResponse(BaseModel):
    id: str
    reading_id: str
    device_id: str
    fire_station_id: str
    distance_km: float  # straight-line
    device_latitude: float
    device_longitude: float
    verification_status: str
    smoke: int
    flame: int
    temperature: Optional[float] = None
    fire_score: Optional[float] = None
    created_at: Optional[str] = None
    # Filled on the station's list
    device_name: Optional[str] = None
    # Filled on the device's list
    station_name: Optional[str] = None
    station_phone: Optional[str] = None


def map_fire_station_to_response(station: MapFireStation) -> MapFireStationResponse:
    return MapFireStationResponse(**asdict(station))


def map_device_to_response(device: MapDevice) -> MapDeviceResponse:
    return MapDeviceResponse(**asdict(device))


def fire_alert_to_response(view: FireAlertView) -> FireAlertResponse:
    return FireAlertResponse(
        **asdict(view.alert),
        device_name=view.device_name,
        station_name=view.station_name,
        station_phone=view.station_phone,
    )
