# FireSight Backend — data_classes package
#
# One ``@dataclass`` per table, mirroring its columns. These are domain models;
# API request/response shapes live in ``app.api.v1.schemas``.
from app.data_layer.data_classes.sensor_reading import SensorReading

__all__ = [
    "SensorReading",
]
