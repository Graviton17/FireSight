"""Pure decision-engine entry points.

Keep sensor fusion and escalation rules here rather than in FastAPI handlers. The
initial function preserves the firmware contract while later changes add the
per-device baseline, camera verdicts, persistence rules, and alarm latch.
"""

from firesight_backend.domain.states import DeviceState
from firesight_backend.schemas.telemetry import TelemetryCommand, TelemetryHeartbeat


def command_for_heartbeat(heartbeat: TelemetryHeartbeat) -> TelemetryCommand:
    if heartbeat.local_alarm:
        return TelemetryCommand(buzzer=True, state=DeviceState.ALARM)
    if not heartbeat.warmup_done:
        return TelemetryCommand(buzzer=False, state=DeviceState.WARMUP)
    return TelemetryCommand(buzzer=False, state=DeviceState.NORMAL)
