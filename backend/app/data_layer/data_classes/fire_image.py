from dataclasses import dataclass
from typing import Optional


@dataclass
class FireImage:
    """A phone-camera snapshot taken for a fire reading (public.fire_images)."""

    id: str
    reading_id: str        # sensor_readings.id, one image per reading
    device_id: str
    bucket: str            # always "fire-images" for now
    storage_path: str      # object path inside the bucket
    content_type: str
    size_bytes: int
    captured_at: str
    created_at: Optional[str] = None
