"""Aggregated v1 API router — include once from ``main.py``."""

from fastapi import APIRouter

from app.api.v1.device_routes import router as device_router
from app.api.v1.fire_station_routes import router as fire_station_router
from app.api.v1.sensor_routes import router as sensor_router

api_router = APIRouter()

api_router.include_router(sensor_router)
api_router.include_router(fire_station_router)
api_router.include_router(device_router)
