from dataclasses import asdict
from typing import List, Optional

from pydantic import BaseModel, Field

from app.api.v1.schemas.fire_station import NearbyFireStationResponse
from app.data_layer.data_classes.sensor_reading import SensorReading

# ESP32 ADC is 12-bit.
_ADC_MAX = 4095


class SensorReadingCreateRequest(BaseModel):
    """Body the ESP32 firmware POSTs (see firmware/firesight_esp32)."""

    device_id: str = Field(min_length=1, max_length=64)
    smoke: int = Field(ge=0, le=_ADC_MAX)
    flame: int = Field(ge=0, le=_ADC_MAX)
    # null when the thermistor reads disconnected/shorted
    temperature: Optional[float] = Field(default=None, ge=-55, le=300)
    fire: bool


class SensorReadingResponse(BaseModel):
    id: str
    device_id: str
    smoke: int
    flame: int
    temperature: Optional[float] = None
    fire: bool
    created_at: Optional[str] = None
    # Filled on POST when fire is true and the device has a location; empty otherwise.
    nearest_fire_stations: List[NearbyFireStationResponse] = []


def sensor_reading_to_response(reading: SensorReading) -> SensorReadingResponse:
    return SensorReadingResponse(**asdict(reading))
