from dataclasses import dataclass
from typing import Optional


@dataclass
class SensorReading:
    """One POST from an ESP32 fire node (public.sensor_readings)."""

    id: str
    device_id: str
    smoke: int                          # MQ-2 raw ADC, 0-4095 (higher = more smoke)
    flame: int                          # flame sensor raw ADC, 0-4095 (lower = flame seen)
    temperature: Optional[float] = None  # °C; None when the NTC reads disconnected/shorted
    fire: bool = False                  # the device's debounced alarm state
    created_at: Optional[str] = None
