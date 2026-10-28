from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class FireDetection:
    """Image-model verdict for one fire image (public.fire_detections)."""

    id: str
    image_id: str               # fire_images.id
    reading_id: str             # sensor_readings.id
    device_id: str
    model: str                  # Hugging Face model id
    label: str                  # top class, e.g. "Fire", "None"
    fire_score: float           # sum of fire-label probabilities, 0-1
    threshold: float            # threshold in force when it ran
    fire_detected: bool         # fire_score >= threshold
    scores: Dict[str, float] = field(default_factory=dict)  # every label -> probability
    inference_ms: int = 0
    created_at: Optional[str] = None
