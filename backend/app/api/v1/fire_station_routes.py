from typing import List, Optional

from fastapi import APIRouter, Query

from app.api.v1.schemas import (
    FireStationCreateRequest,
    FireStationResponse,
    NearbyFireStationResponse,
    PaginatedResponse,
    fire_station_to_response,
    nearby_fire_station_to_response,
)
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
