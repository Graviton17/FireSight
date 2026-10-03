from enum import StrEnum


class DeviceState(StrEnum):
    WARMUP = "WARMUP"
    NORMAL = "NORMAL"
    CHECKING = "CHECKING"
    WARNING = "WARNING"
    ALARM = "ALARM"
