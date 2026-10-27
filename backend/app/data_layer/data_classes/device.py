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
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
