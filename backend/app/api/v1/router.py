"""Aggregated v1 API router — include once from ``main.py``."""

from fastapi import APIRouter

from app.api.v1.sensor_routes import router as sensor_router

api_router = APIRouter()

api_router.include_router(sensor_router)
