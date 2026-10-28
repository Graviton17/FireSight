from dataclasses import asdict
from typing import Optional

from pydantic import BaseModel, Field

from app.data_layer.data_classes.device import Device


class DeviceLocationRequest(BaseModel):
    """Pin a device's location by hand. Wins over the phone's GPS from then on."""

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    name: Optional[str] = Field(default=None, max_length=100)
    address: Optional[str] = Field(default=None, max_length=500)


class DeviceResponse(BaseModel):
    device_id: str
    latitude: float
    longitude: float
    name: Optional[str] = None
    address: Optional[str] = None
    location_source: str = "manual"
    location_accuracy_m: Optional[float] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


def device_to_response(device: Device) -> DeviceResponse:
    return DeviceResponse(**asdict(device))
