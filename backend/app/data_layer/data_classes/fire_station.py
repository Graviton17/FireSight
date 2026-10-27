from dataclasses import dataclass
from typing import Optional


@dataclass
class FireStation:
    """A fire station (public.fire_stations)."""

    id: str
    name: str
    latitude: float
    longitude: float
    place_id: Optional[str] = None       # Google place id; None for manual entries
    address: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    state: str = "Gujarat"
    phone: Optional[str] = None
    google_maps_url: Optional[str] = None
    source: str = "manual"               # 'google_maps' | 'manual'
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class NearbyFireStation:
    """One row of the nearest_fire_stations() RPC."""

    id: str
    name: str
    latitude: float
    longitude: float
    distance_km: float                   # straight-line, not road distance
    address: Optional[str] = None
    city: Optional[str] = None
    phone: Optional[str] = None
    google_maps_url: Optional[str] = None
