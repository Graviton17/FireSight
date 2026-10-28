"""Pydantic request/response models (DTOs) for the v1 HTTP API.

Domain dataclasses stay in ``app.data_layer.data_classes``; this package is
API-boundary only. These models are also the JSON contracts the firmware and
the frontend build against.
"""

from app.api.v1.schemas.common import PaginatedResponse, PaginationParams
from app.api.v1.schemas.fire_image import (
    FireDetectionResponse,
    FireImageResponse,
    fire_detection_to_response,
    fire_image_to_response,
)
from app.api.v1.schemas.sensor_reading import (
    SensorReadingCreateRequest,
    SensorReadingCreateResponse,
    SensorReadingResponse,
    VerificationResponse,
    sensor_reading_to_response,
    verification_to_response,
)

__all__ = [
    # Common
    "PaginatedResponse",
    "PaginationParams",
    # Fire image
    "FireDetectionResponse",
    "FireImageResponse",
    "fire_detection_to_response",
    "fire_image_to_response",
    # Sensor reading
    "SensorReadingCreateRequest",
    "SensorReadingCreateResponse",
    "SensorReadingResponse",
    "VerificationResponse",
    "sensor_reading_to_response",
    "verification_to_response",
]
