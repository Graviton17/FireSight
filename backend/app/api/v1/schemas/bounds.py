from dataclasses import dataclass

from fastapi import HTTPException, Query


@dataclass
class Bounds:
    """Map viewport from query params: ``min_lat, min_lng, max_lat, max_lng``."""

    min_lat: float
    min_lng: float
    max_lat: float
    max_lng: float


def bounds_query(
    min_lat: float = Query(ge=-90, le=90),
    min_lng: float = Query(ge=-180, le=180),
    max_lat: float = Query(ge=-90, le=90),
    max_lng: float = Query(ge=-180, le=180),
) -> Bounds:
    if min_lat > max_lat or min_lng > max_lng:
        raise HTTPException(status_code=422, detail="min_* must not exceed max_*")
    return Bounds(min_lat, min_lng, max_lat, max_lng)
