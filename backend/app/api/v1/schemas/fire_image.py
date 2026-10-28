from dataclasses import asdict
from typing import Dict, Optional

from pydantic import BaseModel

from app.data_layer.data_classes.fire_detection import FireDetection
from app.data_layer.data_classes.fire_image import FireImage


class FireDetectionResponse(BaseModel):
    id: str
    model: str
    label: str
    fire_score: float
    threshold: float
    fire_detected: bool
    scores: Dict[str, float]
    inference_ms: int
    created_at: Optional[str] = None


class FireImageResponse(BaseModel):
    id: str
    reading_id: str
    device_id: str
    bucket: str
    storage_path: str
    content_type: str
    size_bytes: int
    captured_at: str
    created_at: Optional[str] = None
    # Signed, expires after an hour. Null only if signing failed.
    url: Optional[str] = None
    # The image model's verdict; null if the model failed on this image.
    detection: Optional[FireDetectionResponse] = None


def fire_detection_to_response(detection: FireDetection) -> FireDetectionResponse:
    data = asdict(detection)
    for key in ("image_id", "reading_id", "device_id"):
        data.pop(key)
    return FireDetectionResponse(**data)


def fire_image_to_response(
    image: FireImage, url: Optional[str] = None, detection: Optional[FireDetection] = None
) -> FireImageResponse:
    return FireImageResponse(
        **asdict(image),
        url=url,
        detection=fire_detection_to_response(detection) if detection else None,
    )
