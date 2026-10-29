from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.v1.schemas import (
    BoundsResponse,
    DeviceLocationRequest,
    DeviceResponse,
    FireAlertResponse,
    MapDeviceResponse,
    NearbyFireStationResponse,
    PaginatedResponse,
    device_to_response,
    fire_alert_to_response,
    map_device_to_response,
    nearby_fire_station_to_response,
)
from app.api.v1.schemas.bounds import Bounds, bounds_query
from app.services.device_service import DeviceService
from app.services.fire_alert_service import FireAlertService
from app.services.fire_station_service import FireStationService

router = APIRouter(prefix="/devices", tags=["Devices"])


@router.get("/in-bounds", response_model=BoundsResponse[MapDeviceResponse])
async def devices_in_bounds(
    bounds: Bounds = Depends(bounds_query),
    limit: int = Query(default=500, ge=1, le=2000),
):
    """Devices inside the map viewport, each with its latest reading and last alert."""
    devices = await DeviceService.in_bounds(
        bounds.min_lat, bounds.min_lng, bounds.max_lat, bounds.max_lng, limit
    )
    return BoundsResponse[MapDeviceResponse](
        items=[map_device_to_response(d) for d in devices],
        truncated=len(devices) >= limit,
    )


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


@router.get("/{device_id}/alerts", response_model=PaginatedResponse[FireAlertResponse])
async def list_device_alerts(
    device_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """Times this device's alarm went off and the station it called, newest first."""
    alerts, total = await FireAlertService.list_for_device(device_id, page=page, page_size=page_size)
    return PaginatedResponse[FireAlertResponse](
        items=[fire_alert_to_response(a) for a in alerts],
        total=total,
        page=page,
        page_size=page_size,
    )
