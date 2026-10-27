from dataclasses import asdict
from typing import Optional

from pydantic import BaseModel

from app.data_layer.data_classes.fire_image import FireImage


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


def fire_image_to_response(image: FireImage, url: Optional[str] = None) -> FireImageResponse:
    return FireImageResponse(**asdict(image), url=url)
