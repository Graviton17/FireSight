from pydantic import BaseModel, Field

from firesight_backend.domain.states import DeviceState


class TelemetryHeartbeat(BaseModel):
    device_id: str = Field(min_length=1, max_length=64)
    mq2: int = Field(ge=0, le=4095)
    temp_c: float | None = Field(default=None, ge=-40, le=125)
    hum_pct: float | None = Field(default=None, ge=0, le=100)
    warmup_done: bool
    local_alarm: bool = False
    uptime_s: int = Field(ge=0)
    rssi: int | None = None
    fw: str = Field(default="unknown", max_length=32)
    flame_ir: bool | None = None
    flame_ir_raw: int | None = Field(default=None, ge=0, le=4095)
    silenced: bool = False


class TelemetryCommand(BaseModel):
    buzzer: bool
    state: DeviceState
