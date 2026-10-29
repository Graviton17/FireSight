from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.v1.schemas import (
    BoundsResponse,
    FireAlertResponse,
    FireStationCreateRequest,
    FireStationResponse,
    NearbyFireStationResponse,
    PaginatedResponse,
    MapFireStationResponse,
    fire_alert_to_response,
    fire_station_to_response,
    map_fire_station_to_response,
    nearby_fire_station_to_response,
)
from app.api.v1.schemas.bounds import Bounds, bounds_query
from app.services.fire_alert_service import FireAlertService
from app.services.fire_station_service import FireStationService

router = APIRouter(prefix="/fire-stations", tags=["Fire Stations"])


@router.post("", response_model=FireStationResponse, status_code=201)
async def add_fire_station(request_data: FireStationCreateRequest):
    """Add a station by hand."""
    station = await FireStationService.add_station(**request_data.model_dump())
    return fire_station_to_response(station)


@router.get("/nearest", response_model=List[NearbyFireStationResponse])
async def nearest_fire_stations(
    latitude: float = Query(ge=-90, le=90),
    longitude: float = Query(ge=-180, le=180),
    limit: int = Query(default=3, ge=1, le=20),
):
    """Nearest stations to a point, closest first (straight-line distance)."""
    stations = await FireStationService.nearest(latitude, longitude, limit)
    return [nearby_fire_station_to_response(s) for s in stations]


@router.get("/in-bounds", response_model=BoundsResponse[MapFireStationResponse])
async def fire_stations_in_bounds(
    bounds: Bounds = Depends(bounds_query),
    limit: int = Query(default=500, ge=1, le=2000),
):
    """Stations inside the map viewport, with alert counts. Recently called first."""
    stations = await FireStationService.in_bounds(
        bounds.min_lat, bounds.min_lng, bounds.max_lat, bounds.max_lng, limit
    )
    return BoundsResponse[MapFireStationResponse](
        items=[map_fire_station_to_response(s) for s in stations],
        truncated=len(stations) >= limit,
    )


@router.get("", response_model=PaginatedResponse[FireStationResponse])
async def list_fire_stations(
    search: Optional[str] = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
):
    """All stations, alphabetical. ``search`` matches name, city or address."""
    stations, total = await FireStationService.list_stations(
        page=page, page_size=page_size, search=search
    )
    return PaginatedResponse[FireStationResponse](
        items=[fire_station_to_response(s) for s in stations],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{station_id}", response_model=FireStationResponse)
async def get_fire_station(station_id: UUID):
    station = await FireStationService.get(str(station_id))
    if station is None:
        raise HTTPException(status_code=404, detail="Fire station not found")
    return fire_station_to_response(station)


@router.get("/{station_id}/alerts", response_model=PaginatedResponse[FireAlertResponse])
async def list_station_alerts(
    station_id: UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """Alarms that called this station (it was the nearest), newest first."""
    alerts, total = await FireAlertService.list_for_station(
        str(station_id), page=page, page_size=page_size
    )
    return PaginatedResponse[FireAlertResponse](
        items=[fire_alert_to_response(a) for a in alerts],
        total=total,
        page=page,
        page_size=page_size,
    )
