import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from app.core.camera import CameraError, IpWebcamClient
from app.core.storage import FireImageLimits, FireImageStorage
from app.data_layer.crud.fire_detection_crud import FireDetectionCrud
from app.data_layer.crud.fire_image_crud import FireImageCrud
from app.data_layer.data_classes.fire_detection import FireDetection
from app.data_layer.data_classes.fire_image import FireImage
from app.data_layer.data_classes.sensor_reading import SensorReading
from app.data_layer.database_manager import DatabaseManager
from app.telemetries.logger import logger


class FireCaptureService:
    """Phone-camera snapshots: health check, storage, and lookups.

    Capturing and classifying happen in ``FireVerificationService`` while the
    ESP32 waits; this service stores the result afterwards in the
    ``fire-images`` bucket plus a ``fire_images`` row.
    """

    @staticmethod
    def _images_crud() -> FireImageCrud:
        images = DatabaseManager.get_instance().fire_images
        if images is None:
            raise RuntimeError("FireImage CRUD has not been initialised")
        return images

    @staticmethod
    def _detections_crud() -> FireDetectionCrud:
        detections = DatabaseManager.get_instance().fire_detections
        if detections is None:
            raise RuntimeError("FireDetection CRUD has not been initialised")
        return detections

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
    async def store_image(
        reading: SensorReading, image: bytes, captured_at: datetime
    ) -> Optional[FireImage]:
        """Upload *image* and record it for *reading*.

        Runs in the background, so it logs failures instead of raising.
        """
        storage = FireImageStorage()
        object_path = FireImageStorage.object_path_for(reading.device_id, reading.id, captured_at)

        try:
            await storage.upload(object_path=object_path, file_content=image)
        except Exception as e:
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
    async def get_detections_for_images(image_ids: List[str]) -> Dict[str, FireDetection]:
        try:
            return await FireCaptureService._detections_crud().get_by_image_ids(image_ids)
        except Exception as e:
            logger.error("Error getting detections for images", exc_info=e)
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
