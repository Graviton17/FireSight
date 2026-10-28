import asyncio
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, Optional

from app.core.camera import CameraError, IpWebcamClient
from app.core.detection import FireClassifier, FirePrediction
from app.data_layer.data_classes.sensor_reading import SensorReading
from app.data_layer.database_manager import DatabaseManager
from app.services.fire_capture_service import FireCaptureService
from app.static_memory_cache import StaticMemoryCache
from app.telemetries.logger import logger

# not_needed  : sensors said no fire, nothing to verify          -> buzz false
# confirmed   : the image model also sees fire/smoke             -> buzz true
# rejected    : the image model sees no fire                     -> buzz false
# unavailable : camera / model / timeout problem, can't verify   -> buzz true (fail-safe)
VerificationStatus = Literal["not_needed", "confirmed", "rejected", "unavailable"]


@dataclass
class Verification:
    status: VerificationStatus
    buzz: bool
    latency_ms: int = 0
    reason: Optional[str] = None             # why it was unavailable
    prediction: Optional[FirePrediction] = None
    image: Optional[bytes] = None            # kept to store after the response
    captured_at: Optional[datetime] = None


def _unavailable(reason: str, started: float, **kwargs) -> Verification:
    # Fail-safe: the sensors already agreed on fire, so a broken camera or
    # model must never silence the alarm.
    return Verification(
        status="unavailable",
        buzz=True,
        latency_ms=round((time.monotonic() - started) * 1000),
        reason=reason,
        **kwargs,
    )


class FireVerificationService:
    """Second verification: confirm the sensors' fire with the phone camera.

    Runs only when the ESP32 reports ``fire: true``, inside the POST, and
    decides ``buzz``. Capture + inference must finish within
    ``detection.timeout_seconds`` (the ESP32 gives up after 5 s).
    """

    @staticmethod
    async def verify(fire: bool) -> Verification:
        if not fire:
            return Verification(status="not_needed", buzz=False)

        started = time.monotonic()
        timeout = StaticMemoryCache.get_verification_timeout_seconds()
        try:
            return await asyncio.wait_for(FireVerificationService._capture_and_classify(started), timeout)
        except TimeoutError:
            return _unavailable(f"camera + model took longer than {timeout:g}s", started)

    @staticmethod
    async def _capture_and_classify(started: float) -> Verification:
        classifier = FireClassifier.get()
        if classifier is None:
            return _unavailable("fire model not loaded", started)

        camera = IpWebcamClient.from_config()
        if camera is None:
            return _unavailable("camera not configured", started)

        try:
            image = await camera.capture_jpeg()
        except CameraError as e:
            return _unavailable(str(e), started)
        captured_at = datetime.now(UTC)

        try:
            prediction = await asyncio.to_thread(classifier.predict, image)
        except Exception as e:
            logger.error("Fire model inference failed", exc_info=e)
            # Keep the image: it is still evidence of what the camera saw.
            return _unavailable("fire model error", started, image=image, captured_at=captured_at)

        return Verification(
            status="confirmed" if prediction.fire_detected else "rejected",
            buzz=prediction.fire_detected,
            latency_ms=round((time.monotonic() - started) * 1000),
            prediction=prediction,
            image=image,
            captured_at=captured_at,
        )

    @staticmethod
    async def store(reading: SensorReading, verification: Verification) -> None:
        """Background task after the response: store the image and the model's verdict."""
        if verification.image is None or verification.captured_at is None:
            return

        image = await FireCaptureService.store_image(reading, verification.image, verification.captured_at)
        prediction = verification.prediction
        if image is None or prediction is None:
            return

        detections = DatabaseManager.get_instance().fire_detections
        if detections is None:
            logger.error("FireDetection CRUD has not been initialised")
            return
        try:
            await detections.create_detection(
                image_id=image.id,
                reading_id=reading.id,
                device_id=reading.device_id,
                model=prediction.model,
                label=prediction.label,
                fire_score=prediction.fire_score,
                threshold=prediction.threshold,
                fire_detected=prediction.fire_detected,
                scores=prediction.scores,
                inference_ms=prediction.inference_ms,
            )
        except Exception as e:
            logger.error("Fire detection record failed", reading_id=reading.id, exc_info=e)
