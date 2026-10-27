from dataclasses import asdict
from typing import Optional

from pydantic import BaseModel, Field

from app.data_layer.data_classes.fire_station import FireStation, NearbyFireStation


class FireStationCreateRequest(BaseModel):
    """Add a station by hand (one the scrape missed)."""

    name: str = Field(min_length=1, max_length=200)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    address: Optional[str] = Field(default=None, max_length=500)
    city: Optional[str] = Field(default=None, max_length=100)
    postal_code: Optional[str] = Field(default=None, max_length=20)
    phone: Optional[str] = Field(default=None, max_length=50)
    google_maps_url: Optional[str] = Field(default=None, max_length=1000)


class FireStationResponse(BaseModel):
    id: str
    name: str
    latitude: float
    longitude: float
    place_id: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    state: str
    phone: Optional[str] = None
    google_maps_url: Optional[str] = None
    source: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class NearbyFireStationResponse(BaseModel):
    id: str
    name: str
    latitude: float
    longitude: float
    distance_km: float  # straight-line
    address: Optional[str] = None
    city: Optional[str] = None
    phone: Optional[str] = None
    google_maps_url: Optional[str] = None


def fire_station_to_response(station: FireStation) -> FireStationResponse:
    return FireStationResponse(**asdict(station))


def nearby_fire_station_to_response(station: NearbyFireStation) -> NearbyFireStationResponse:
    return NearbyFireStationResponse(**asdict(station))
