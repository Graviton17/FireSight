import time
from datetime import UTC, datetime
from typing import Dict, List, Optional, Tuple

from app.core.camera import CameraError, IpWebcamClient
from app.core.storage import FireImageLimits, FireImageStorage
from app.data_layer.crud.fire_image_crud import FireImageCrud
from app.data_layer.data_classes.fire_image import FireImage
from app.data_layer.data_classes.sensor_reading import SensorReading
from app.data_layer.database_manager import DatabaseManager
from app.static_memory_cache import StaticMemoryCache
from app.telemetries.logger import logger

# device_id -> time.monotonic() of the last capture slot handed out. In-memory:
# a restart just allows one extra capture.
_last_capture_at: Dict[str, float] = {}


class FireCaptureService:
    """Grab a snapshot from the phone camera when a device reports fire.

    Routes call :meth:`claim_capture_slot` synchronously, then run
    :meth:`capture_for_reading` as a background task so the ESP32 gets its
    response without waiting for the phone or the upload. Each stored image
    gets a row in ``fire_images`` linking it to its reading.
    """

    @staticmethod
    def _images_crud() -> FireImageCrud:
        images = DatabaseManager.get_instance().fire_images
        if images is None:
            raise RuntimeError("FireImage CRUD has not been initialised")
        return images

    @staticmethod
    async def check_camera() -> bool:
        """Take one test snapshot (not stored) and log whether the phone camera works."""
        camera = IpWebcamClient.from_config()
        if camera is None:
            logger.warning(
                "Camera not configured: fire images are disabled. Set camera.base_url in config.json."
            )
            return False

        started = time.monotonic()
        try:
            image = await camera.capture_jpeg()
        except CameraError as e:
            logger.error(
                "Camera check FAILED: fire images will not be captured until it is reachable",
                url=camera.snapshot_url,
                error=str(e),
            )
            return False

        logger.info(
            "Camera check OK",
            url=camera.snapshot_url,
            bytes=len(image),
            ms=round((time.monotonic() - started) * 1000),
        )
        return True

    @staticmethod
    def claim_capture_slot(device_id: str) -> bool:
        """True if this reading should trigger a capture.

        At most one capture per device per ``camera.capture_interval_seconds``;
        the firmware re-posts every few seconds while the alarm is on. No await
        between the check and the write, so concurrent requests can't both win.
        """
        if not StaticMemoryCache.get_camera_base_url():
            return False
        now = time.monotonic()
        last = _last_capture_at.get(device_id)
        if last is not None and now - last < StaticMemoryCache.get_camera_capture_interval_seconds():
            return False
        _last_capture_at[device_id] = now
        return True

    @staticmethod
    def release_capture_slot(device_id: str) -> None:
        """Forget a failed capture so the next fire reading retries straight away."""
        _last_capture_at.pop(device_id, None)

    @staticmethod
    async def capture_for_reading(reading: SensorReading) -> Optional[FireImage]:
        """Capture, upload and record an image for *reading*.

        Runs in the background, so it logs failures instead of raising.
        """
        camera = IpWebcamClient.from_config()
        if camera is None:
            return None

        try:
            image = await camera.capture_jpeg()
        except CameraError as e:
            FireCaptureService.release_capture_slot(reading.device_id)
            logger.error("Fire image capture failed", device_id=reading.device_id, error=str(e))
            return None

        captured_at = datetime.now(UTC)
        storage = FireImageStorage()
        object_path = FireImageStorage.object_path_for(reading.device_id, reading.id, captured_at)

        try:
            await storage.upload(object_path=object_path, file_content=image)
        except Exception as e:
            FireCaptureService.release_capture_slot(reading.device_id)
            logger.error("Fire image upload failed", device_id=reading.device_id, exc_info=e)
            return None

        try:
            fire_image = await FireCaptureService._images_crud().create_image(
                reading_id=reading.id,
                device_id=reading.device_id,
                bucket=storage.bucket_name,
                storage_path=object_path,
                content_type=FireImageLimits.CONTENT_TYPE,
                size_bytes=len(image),
                captured_at=captured_at.isoformat(),
            )
        except Exception as e:
            # Don't leave an object in the bucket that no row points to.
            await storage.delete(object_path)
            FireCaptureService.release_capture_slot(reading.device_id)
            logger.error("Fire image record failed", device_id=reading.device_id, exc_info=e)
            return None

        logger.info(
            "Fire image stored",
            device_id=reading.device_id,
            reading_id=reading.id,
            image_id=fire_image.id,
            path=object_path,
            bytes=len(image),
        )
        return fire_image

    @staticmethod
    async def get_images_for_readings(reading_ids: List[str]) -> Dict[str, FireImage]:
        try:
            return await FireCaptureService._images_crud().get_by_reading_ids(reading_ids)
        except Exception as e:
            logger.error("Error getting fire images for readings", exc_info=e)
            raise

    @staticmethod
    async def list_images(
        device_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[FireImage], int]:
        try:
            return await FireCaptureService._images_crud().list_for_device(
                device_id, page=page, page_size=page_size
            )
        except Exception as e:
            logger.error("Error listing fire images", device_id=device_id, exc_info=e)
            raise

    @staticmethod
    async def signed_url(image: FireImage) -> Optional[str]:
        return await FireImageStorage().signed_url(image.storage_path)
