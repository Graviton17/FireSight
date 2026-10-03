from fastapi import APIRouter

from firesight_backend.api.routes import health, telemetry

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(telemetry.router, tags=["telemetry"])
