from dataclasses import dataclass
from typing import Optional


@dataclass
class Device:
    """Where an ESP32 node is installed (public.devices)."""

    device_id: str
    latitude: float
    longitude: float
    name: Optional[str] = None
    address: Optional[str] = None
    location_source: str = "manual"            # 'manual' | 'phone_gps'
    location_accuracy_m: Optional[float] = None  # phone fix accuracy; None for manual
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
