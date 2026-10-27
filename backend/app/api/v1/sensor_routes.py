import asyncio
from dataclasses import asdict
from typing import List

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from app.api.v1.schemas import (
    FireImageResponse,
    PaginatedResponse,
    SensorReadingCreateRequest,
    SensorReadingCreateResponse,
    SensorReadingResponse,
    fire_image_to_response,
    sensor_reading_to_response,
)
from app.data_layer.data_classes.fire_image import FireImage
from app.data_layer.data_classes.sensor_reading import SensorReading
from app.services.fire_capture_service import FireCaptureService
from app.services.sensor_reading_service import SensorReadingService

router = APIRouter(prefix="/sensor-data", tags=["Sensor Data"])


async def _signed_images(images: List[FireImage]) -> List[FireImageResponse]:
    urls = await asyncio.gather(*(FireCaptureService.signed_url(image) for image in images))
    return [fire_image_to_response(image, url) for image, url in zip(images, urls, strict=True)]


async def _readings_with_images(readings: List[SensorReading]) -> List[SensorReadingResponse]:
    # One query for the page; only fire rows have images, so signing is cheap.
    by_reading = await FireCaptureService.get_images_for_readings([r.id for r in readings])
    signed = {image.reading_id: image for image in await _signed_images(list(by_reading.values()))}
    return [sensor_reading_to_response(r, signed.get(r.id)) for r in readings]


@router.post("", response_model=SensorReadingCreateResponse, status_code=201)
async def create_sensor_reading(request_data: SensorReadingCreateRequest, background_tasks: BackgroundTasks):
    """Store one reading from an ESP32.

    On ``fire: true`` a phone-camera snapshot is captured in the background
    after the response is sent, so the device's short HTTP timeout is safe.
    """
    reading = await SensorReadingService.record_reading(
        device_id=request_data.device_id,
        smoke=request_data.smoke,
        flame=request_data.flame,
        temperature=request_data.temperature,
        fire=request_data.fire,
    )

    capture = reading.fire and FireCaptureService.claim_capture_slot(reading.device_id)
    if capture:
        background_tasks.add_task(FireCaptureService.capture_for_reading, reading)

    return SensorReadingCreateResponse(**asdict(reading), image_capture_scheduled=capture)


@router.get("/{device_id}/latest", response_model=SensorReadingResponse)
async def get_latest_reading(device_id: str):
    """Most recent reading for a device."""
    reading = await SensorReadingService.get_latest(device_id)
    if reading is None:
        raise HTTPException(status_code=404, detail="No readings for this device")
    return (await _readings_with_images([reading]))[0]


@router.get("/{device_id}/images", response_model=PaginatedResponse[FireImageResponse])
async def list_fire_images(
    device_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """Fire snapshots for a device, newest first, each with a signed URL."""
    images, total = await FireCaptureService.list_images(device_id, page=page, page_size=page_size)
    return PaginatedResponse[FireImageResponse](
        items=await _signed_images(images),
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{device_id}", response_model=PaginatedResponse[SensorReadingResponse])
async def list_readings(
    device_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
):
    """Reading history for a device, newest first."""
    readings, total = await SensorReadingService.list_readings(
        device_id, page=page, page_size=page_size
    )
    return PaginatedResponse[SensorReadingResponse](
        items=await _readings_with_images(readings),
        total=total,
        page=page,
        page_size=page_size,
    )
