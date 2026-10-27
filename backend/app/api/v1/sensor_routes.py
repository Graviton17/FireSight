from fastapi import APIRouter, HTTPException, Query

from app.api.v1.schemas import (
    PaginatedResponse,
    SensorReadingCreateRequest,
    SensorReadingResponse,
    sensor_reading_to_response,
)
from app.services.sensor_reading_service import SensorReadingService

router = APIRouter(prefix="/sensor-data", tags=["Sensor Data"])


@router.post("", response_model=SensorReadingResponse, status_code=201)
async def create_sensor_reading(request_data: SensorReadingCreateRequest):
    """Store one reading from an ESP32."""
    reading = await SensorReadingService.record_reading(
        device_id=request_data.device_id,
        smoke=request_data.smoke,
        flame=request_data.flame,
        temperature=request_data.temperature,
        fire=request_data.fire,
    )
    return sensor_reading_to_response(reading)


@router.get("/{device_id}/latest", response_model=SensorReadingResponse)
async def get_latest_reading(device_id: str):
    """Most recent reading for a device."""
    reading = await SensorReadingService.get_latest(device_id)
    if reading is None:
        raise HTTPException(status_code=404, detail="No readings for this device")
    return sensor_reading_to_response(reading)


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
        items=[sensor_reading_to_response(r) for r in readings],
        total=total,
        page=page,
        page_size=page_size,
    )
