"""Table name constants for FireSight database tables."""


class TablesNameConstant:
    """Constants for FireSight table names.

    Add a constant here for every new table, then reference it from its CRUD
    class — never hard-code table names elsewhere.
    """

    SENSOR_READINGS = "sensor_readings"
    FIRE_STATIONS = "fire_stations"
    DEVICES = "devices"
    FIRE_IMAGES = "fire_images"
    FIRE_DETECTIONS = "fire_detections"


class RpcFunctionsConstant:
    """Postgres functions called over PostgREST RPC."""

    NEAREST_FIRE_STATIONS = "nearest_fire_stations"
