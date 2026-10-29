"""Fire/smoke image classifier — the second verification after the sensors.

Wraps a Hugging Face image-classification model
(``prithivMLmods/Fire-Detection-Siglip2``, labels ``fire``, ``normal``,
``smoke``; 99.4% accuracy on its own test set). Loaded once at startup from a local
folder (``backend/models/...``, see README) so the server needs no internet
and never downloads at startup.

torch / transformers are imported lazily so the rest of the app (and the
tests) run without them.
"""

from __future__ import annotations

import io
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.static_memory_cache import StaticMemoryCache
from app.telemetries.logger import logger

DEFAULT_MODEL_PATH = "models/Fire-Detection-Siglip2"
# Relative model paths are resolved against backend/, not the working directory.
_BACKEND_DIR = Path(__file__).resolve().parents[3]
DEFAULT_FIRE_LABELS = ["fire", "smoke"]


@dataclass
class FirePrediction:
    model: str
    label: str                  # top class
    fire_score: float           # sum of fire-label probabilities, 0-1
    threshold: float
    fire_detected: bool         # fire_score >= threshold
    scores: Dict[str, float]    # every label -> probability
    inference_ms: int


class FireClassifier:
    _instance: Optional["FireClassifier"] = None

    def __init__(self, model_path: str, fire_labels: List[str], device: str = "cpu"):
        import torch
        from transformers import AutoImageProcessor, AutoModelForImageClassification

        path = Path(model_path)
        if not path.is_absolute():
            path = _BACKEND_DIR / path
        if not (path / "model.safetensors").is_file():
            raise FileNotFoundError(
                f"No model.safetensors in {path} — see README 'Fire model' to download it"
            )

        self._torch = torch
        self.model_id = path.name
        self.device = device
        # local_files_only: never reach out to the Hub at runtime.
        self.processor: Any = AutoImageProcessor.from_pretrained(path, local_files_only=True)
        self.model: Any = (
            AutoModelForImageClassification.from_pretrained(path, local_files_only=True).to(device).eval()
        )
        self.id2label: Dict[int, str] = {int(k): v for k, v in self.model.config.id2label.items()}

        unknown = set(fire_labels) - set(self.id2label.values())
        if unknown:
            model_labels = sorted(self.id2label.values())
            raise ValueError(f"detection.fire_labels {sorted(unknown)} not in model labels {model_labels}")
        self.fire_labels = list(fire_labels)
        # One inference at a time; torch already uses every core for a single image.
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    @classmethod
    def load_from_config(cls) -> Optional["FireClassifier"]:
        """Load the model named in config.json ``detection``. Blocking — call from a thread.

        Returns ``None`` (and logs why) when disabled or the load fails; the
        verification then reports ``unavailable`` and the ESP32 is told to buzz.
        """
        if StaticMemoryCache.get_config("detection", "enabled") is False:
            logger.warning("Fire model disabled (detection.enabled = false): fire is not image-verified")
            cls._instance = None
            return None

        model_path = StaticMemoryCache.get_config("detection", "model_path") or DEFAULT_MODEL_PATH
        fire_labels = StaticMemoryCache.get_config("detection", "fire_labels") or DEFAULT_FIRE_LABELS
        device = StaticMemoryCache.get_config("detection", "device") or "cpu"

        started = time.monotonic()
        try:
            classifier = cls(model_path, fire_labels, device)
            classifier.warm_up()
        except Exception as e:
            logger.error(
                "Fire model FAILED to load: fire is not image-verified", model=model_path, exc_info=e
            )
            cls._instance = None
            return None

        cls._instance = classifier
        logger.info(
            "Fire model loaded",
            model=model_path,
            device=device,
            labels=list(classifier.id2label.values()),
            fire_labels=classifier.fire_labels,
            threshold=StaticMemoryCache.get_detection_threshold(),
            seconds=round(time.monotonic() - started, 1),
        )
        return classifier

    @classmethod
    def get(cls) -> Optional["FireClassifier"]:
        return cls._instance

    def warm_up(self) -> None:
        """First inference is slow (lazy init); pay it at startup, not during a fire."""
        from PIL import Image

        buffer = io.BytesIO()
        Image.new("RGB", (224, 224)).save(buffer, format="JPEG")
        self.predict(buffer.getvalue())

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def predict(self, jpeg: bytes) -> FirePrediction:
        """Classify one JPEG. Blocking and CPU-bound — call via ``asyncio.to_thread``."""
        from PIL import Image

        image = Image.open(io.BytesIO(jpeg)).convert("RGB")
        threshold = StaticMemoryCache.get_detection_threshold()

        started = time.monotonic()
        with self._lock, self._torch.inference_mode():
            inputs = self.processor(images=image, return_tensors="pt").to(self.device)
            probabilities = self.model(**inputs).logits[0].softmax(-1).tolist()
        inference_ms = round((time.monotonic() - started) * 1000)

        scores = {self.id2label[i]: round(p, 4) for i, p in enumerate(probabilities)}
        fire_score = round(min(1.0, sum(scores[label] for label in self.fire_labels)), 4)
        fire_detected = fire_score >= threshold
        if StaticMemoryCache.get_detection_force_fire() and not fire_detected:
            # Real scores are kept; only the verdict is overridden.
            logger.warning(
                "detection.force_fire is on: reporting fire regardless of the image",
                fire_score=fire_score,
                threshold=threshold,
            )
            fire_detected = True
        return FirePrediction(
            model=self.model_id,
            label=max(scores, key=lambda label: scores[label]),
            fire_score=fire_score,
            threshold=threshold,
            fire_detected=fire_detected,
            scores=scores,
            inference_ms=inference_ms,
        )
