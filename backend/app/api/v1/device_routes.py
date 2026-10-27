from typing import List

from fastapi import APIRouter, HTTPException, Query

from app.api.v1.schemas import (
    DeviceLocationRequest,
    DeviceResponse,
    NearbyFireStationResponse,
    device_to_response,
    nearby_fire_station_to_response,
)
from app.services.device_service import DeviceService
from app.services.fire_station_service import FireStationService

router = APIRouter(prefix="/devices", tags=["Devices"])


@router.put("/{device_id}", response_model=DeviceResponse)
async def set_device_location(device_id: str, request_data: DeviceLocationRequest):
    """Register (or move) a device's install location."""
    device = await DeviceService.set_location(device_id=device_id, **request_data.model_dump())
    return device_to_response(device)


@router.get("/{device_id}", response_model=DeviceResponse)
async def get_device(device_id: str):
    device = await DeviceService.get(device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device has no registered location")
    return device_to_response(device)


@router.get("/{device_id}/nearest-fire-stations", response_model=List[NearbyFireStationResponse])
async def nearest_fire_stations_for_device(
    device_id: str,
    limit: int = Query(default=3, ge=1, le=20),
):
    """Nearest stations to where this device is installed, closest first."""
    stations = await FireStationService.nearest_to_device(device_id, limit)
    if stations is None:
        raise HTTPException(status_code=404, detail="Device has no registered location")
    return [nearby_fire_station_to_response(s) for s in stations]
