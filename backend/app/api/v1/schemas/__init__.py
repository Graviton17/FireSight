"""Pydantic request/response models (DTOs) for the v1 HTTP API.

Domain dataclasses stay in ``app.data_layer.data_classes``; this package is
API-boundary only. These models are also the JSON contracts the firmware and
the frontend build against.
"""

from app.api.v1.schemas.common import PaginatedResponse, PaginationParams
from app.api.v1.schemas.sensor_reading import (
    SensorReadingCreateRequest,
    SensorReadingResponse,
    sensor_reading_to_response,
)

__all__ = [
    # Common
    "PaginatedResponse",
    "PaginationParams",
    # Sensor reading
    "SensorReadingCreateRequest",
    "SensorReadingResponse",
    "sensor_reading_to_response",
]
