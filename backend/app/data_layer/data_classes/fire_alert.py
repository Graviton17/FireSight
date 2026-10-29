from dataclasses import dataclass
from typing import Optional


@dataclass
class FireAlert:
    """A buzzing alarm and the nearest station it went to (public.fire_alerts)."""

    id: str
    reading_id: str
    device_id: str
    fire_station_id: str
    distance_km: float                    # straight-line, not road distance
    device_latitude: float
    device_longitude: float
    verification_status: str             # 'confirmed' | 'unavailable'
    smoke: int
    flame: int
    temperature: Optional[float] = None
    fire_score: Optional[float] = None   # None when the model couldn't run
    created_at: Optional[str] = None
