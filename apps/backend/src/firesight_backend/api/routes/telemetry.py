from fastapi import APIRouter, Header, HTTPException, status

from firesight_backend.core.config import settings
from firesight_backend.schemas.telemetry import TelemetryCommand, TelemetryHeartbeat
from firesight_backend.services.decision_engine import command_for_heartbeat

router = APIRouter()


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")


@router.post("/telemetry", response_model=TelemetryCommand)
async def receive_telemetry(
    heartbeat: TelemetryHeartbeat, x_api_key: str | None = Header(default=None)
) -> TelemetryCommand:
    """Accept an ESP32 heartbeat and return the current buzzer command.

    Persistence and the full per-device decision engine are intentionally introduced
    behind this boundary, keeping the wire contract stable for firmware development.
    """
    require_api_key(x_api_key)
    return command_for_heartbeat(heartbeat)
