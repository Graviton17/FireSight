from dataclasses import asdict
from typing import Dict, Optional

from pydantic import BaseModel, Field

from app.api.v1.schemas.fire_image import FireImageResponse
from app.data_layer.data_classes.sensor_reading import SensorReading
from app.services.fire_verification_service import Verification, VerificationStatus

# ESP32 ADC is 12-bit.
_ADC_MAX = 4095


class SensorReadingCreateRequest(BaseModel):
    """Body the ESP32 firmware POSTs (see firmware/firesight_esp32)."""

    device_id: str = Field(min_length=1, max_length=64)
    smoke: int = Field(ge=0, le=_ADC_MAX)
    flame: int = Field(ge=0, le=_ADC_MAX)
    # null when the thermistor reads disconnected/shorted
    temperature: Optional[float] = Field(default=None, ge=-55, le=300)
    fire: bool


class SensorReadingResponse(BaseModel):
    id: str
    device_id: str
    smoke: int
    flame: int
    temperature: Optional[float] = None
    fire: bool
    created_at: Optional[str] = None
    # The fire_images row for this reading, if one was captured. Only filled on GET.
    image: Optional[FireImageResponse] = None


class VerificationResponse(BaseModel):
    """Second verification by the image model. See FireVerificationService."""

    status: VerificationStatus
    latency_ms: int
    reason: Optional[str] = None             # set when status is "unavailable"
    label: Optional[str] = None              # top class, e.g. "Fire", "None"
    fire_score: Optional[float] = None
    threshold: Optional[float] = None
    scores: Optional[Dict[str, float]] = None


class SensorReadingCreateResponse(SensorReadingResponse):
    # What the ESP32 acts on: sound the buzzer or not.
    buzz: bool
    verification: VerificationResponse


def sensor_reading_to_response(
    reading: SensorReading, image: Optional[FireImageResponse] = None
) -> SensorReadingResponse:
    return SensorReadingResponse(**asdict(reading), image=image)


def verification_to_response(verification: Verification) -> VerificationResponse:
    prediction = verification.prediction
    return VerificationResponse(
        status=verification.status,
        latency_ms=verification.latency_ms,
        reason=verification.reason,
        label=prediction.label if prediction else None,
        fire_score=prediction.fire_score if prediction else None,
        threshold=prediction.threshold if prediction else None,
        scores=prediction.scores if prediction else None,
    )
