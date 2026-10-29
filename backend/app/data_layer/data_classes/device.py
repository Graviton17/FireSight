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


@dataclass
class MapDevice:
    """One row of the devices_in_bounds() RPC: a device and its latest status."""

    device_id: str
    latitude: float
    longitude: float
    name: Optional[str] = None
    address: Optional[str] = None
    location_source: str = "manual"
    location_accuracy_m: Optional[float] = None
    last_reading_at: Optional[str] = None      # None if it never reported
    last_fire: Optional[bool] = None
    last_smoke: Optional[int] = None
    last_flame: Optional[int] = None
    last_temperature: Optional[float] = None
    last_alert_at: Optional[str] = None
    alert_count: int = 0
