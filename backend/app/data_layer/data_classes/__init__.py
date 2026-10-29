# FireSight Backend — data_classes package
#
# One ``@dataclass`` per table, mirroring its columns. These are domain models;
# API request/response shapes live in ``app.api.v1.schemas``.
from app.data_layer.data_classes.device import Device, MapDevice
from app.data_layer.data_classes.fire_alert import FireAlert
from app.data_layer.data_classes.fire_detection import FireDetection
from app.data_layer.data_classes.fire_image import FireImage
from app.data_layer.data_classes.fire_station import FireStation, MapFireStation, NearbyFireStation
from app.data_layer.data_classes.sensor_reading import SensorReading

__all__ = [
    "Device",
    "FireAlert",
    "FireDetection",
    "FireImage",
    "FireStation",
    "MapDevice",
    "MapFireStation",
    "NearbyFireStation",
    "SensorReading",
]
