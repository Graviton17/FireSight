import asyncio
from dataclasses import asdict
from typing import List

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from app.api.v1.schemas import (
    FireImageResponse,
    IncidentResolveResponse,
    PaginatedResponse,
    SensorReadingCreateRequest,
    SensorReadingCreateResponse,
    SensorReadingResponse,
    fire_image_to_response,
    nearby_fire_station_to_response,
    sensor_reading_to_response,
    verification_to_response,
)
from app.data_layer.data_classes.fire_image import FireImage
from app.data_layer.data_classes.fire_station import NearbyFireStation
from app.data_layer.data_classes.sensor_reading import SensorReading
from app.services.fire_alert_service import FireAlertService
from app.services.fire_capture_service import FireCaptureService
from app.services.fire_station_service import FireStationService
from app.services.fire_verification_service import FireVerificationService, Verification
from app.services.live_events import LiveEvents
from app.services.sensor_reading_service import SensorReadingService
from app.telemetries.logger import logger

router = APIRouter(prefix="/sensor-data", tags=["Sensor Data"])


async def _signed_images(images: List[FireImage]) -> List[FireImageResponse]:
    if not images:
        return []
    urls, detections = await asyncio.gather(
        asyncio.gather(*(FireCaptureService.signed_url(image) for image in images)),
        FireCaptureService.get_detections_for_images([image.id for image in images]),
    )
    return [
        fire_image_to_response(image, url, detections.get(image.id))
        for image, url in zip(images, urls, strict=True)
    ]


async def _readings_with_images(readings: List[SensorReading]) -> List[SensorReadingResponse]:
    # One query for the page; only fire rows have images, so signing is cheap.
    by_reading = await FireCaptureService.get_images_for_readings([r.id for r in readings])
    signed = {image.reading_id: image for image in await _signed_images(list(by_reading.values()))}
    return [sensor_reading_to_response(r, signed.get(r.id)) for r in readings]


async def _nearest_stations(device_id: str, fire: bool) -> List[NearbyFireStation]:
    if not fire:
        return []
    return await FireStationService.nearest_for_alarm(device_id)


async def _verify(device_id: str, fire: bool) -> Verification:
    # A live incident is already confirmed: keep buzzing, no new photo.
    if fire and await FireAlertService.live_for_device(device_id) is not None:
        return Verification(status="incident_live", buzz=True)
    return await FireVerificationService.verify(fire)


@router.post("", response_model=SensorReadingCreateResponse, status_code=201)
async def create_sensor_reading(request_data: SensorReadingCreateRequest, background_tasks: BackgroundTasks):
    """Store one reading from an ESP32 and tell it whether to buzz.

    On ``fire: true`` the phone camera snapshot is checked by the image model
    (second verification) before answering; ``buzz`` is the final decision.
    When it buzzes, the nearest fire stations come back too.
    While the device has a live incident (confirmed, button not pressed yet)
    the camera is skipped and the answer is always ``buzz: true``.
    The image, verdict and the alert (which station was called) are stored
    after the response is sent.
    """
    # Saving the reading, verifying and the station lookup run side by side:
    # the ESP32 gives up after 5 s and verification alone may take 4.
    reading, verification, stations = await asyncio.gather(
        SensorReadingService.record_reading(
            device_id=request_data.device_id,
            smoke=request_data.smoke,
            flame=request_data.flame,
            temperature=request_data.temperature,
            fire=request_data.fire,
        ),
        _verify(request_data.device_id, request_data.fire),
        _nearest_stations(request_data.device_id, request_data.fire),
    )

    if verification.status not in ("not_needed", "incident_live"):
        prediction = verification.prediction
        logger.warning(
            "Fire verification",
            device_id=reading.device_id,
            status=verification.status,
            buzz=verification.buzz,
            label=prediction.label if prediction else None,
            fire_score=prediction.fire_score if prediction else None,
            reason=verification.reason,
            latency_ms=verification.latency_ms,
        )
    LiveEvents.publish("reading", reading.device_id)
    # The call first: it shouldn't wait on the snapshot upload.
    if verification.buzz and stations and verification.status != "incident_live":
        background_tasks.add_task(FireAlertService.record, reading, verification, stations)
    if verification.image is not None:
        background_tasks.add_task(FireVerificationService.store, reading, verification)

    return SensorReadingCreateResponse(
        **asdict(reading),
        buzz=verification.buzz,
        verification=verification_to_response(verification),
        # The model rejecting the fire means no alarm, so no stations to call.
        nearest_fire_stations=(
            [nearby_fire_station_to_response(s) for s in stations] if verification.buzz else []
        ),
    )


@router.post("/{device_id}/resolve", response_model=IncidentResolveResponse)
async def resolve_incident(device_id: str):
    """The button on the device was pressed: the fire is handled.

    Closes the device's live incident; its next fire is a new one, checked
    by the camera again.
    """
    resolved = await FireAlertService.resolve(device_id)
    logger.warning("Incident resolved", device_id=device_id, resolved=len(resolved))
    if resolved:
        LiveEvents.publish("alert", device_id)
    return IncidentResolveResponse(resolved=len(resolved))


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
