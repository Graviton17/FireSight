"""Singleton DatabaseManager — initialises Supabase and all CRUD instances.

  1. Call ``await DatabaseManager.initialize(url, key)`` once at startup.
  2. Anywhere else: ``DatabaseManager.get_instance()`` returns the ready manager.
  3. Add new CRUD attributes here as new tables are introduced.
"""

from typing import Optional, Tuple

from app.data_layer.crud.device_crud import DeviceCrud
from app.data_layer.crud.fire_image_crud import FireImageCrud
from app.data_layer.crud.fire_station_crud import FireStationCrud
from app.data_layer.crud.sensor_reading_crud import SensorReadingCrud
from app.data_layer.supabase_client import SupabaseClient
from app.data_layer.supabase_credentials import resolve_supabase_key


class DatabaseManager:
    _instance: Optional["DatabaseManager"] = None

    # ------------------------------------------------------------------
    # Key resolution
    # ------------------------------------------------------------------

    @staticmethod
    def resolve_server_supabase_key() -> Tuple[str, bool]:
        """Prefer the Supabase **service_role** key for backend writes."""
        return resolve_supabase_key("database", prefer_service_role=True)

    # ------------------------------------------------------------------
    # Type annotations for CRUD attributes (add as tables are created)
    # ------------------------------------------------------------------
    supabase: Optional[SupabaseClient]
    sensor_readings: Optional[SensorReadingCrud]
    fire_stations: Optional[FireStationCrud]
    devices: Optional[DeviceCrud]
    fire_images: Optional[FireImageCrud]

    def __init__(self) -> None:
        self.supabase = None
        self.sensor_readings = None
        self.fire_stations = None
        self.devices = None
        self.fire_images = None

    # ------------------------------------------------------------------
    # Async initialisation
    # ------------------------------------------------------------------

    @classmethod
    async def initialize(cls, supabase_url: str, supabase_key: str) -> None:
        if cls._instance is None:
            manager = cls()
            await manager._async_init(supabase_url, supabase_key)
            cls._instance = manager

    async def _async_init(self, supabase_url: str, supabase_key: str) -> None:
        self.supabase = await SupabaseClient.create(supabase_url, supabase_key)
        self.sensor_readings = SensorReadingCrud(self.supabase)
        self.fire_stations = FireStationCrud(self.supabase)
        self.devices = DeviceCrud(self.supabase)
        self.fire_images = FireImageCrud(self.supabase)

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get_supabase_client(self) -> SupabaseClient:
        if self.supabase is None:
            raise RuntimeError("Supabase client has not been initialised")
        return self.supabase

    @classmethod
    def get_instance(cls) -> "DatabaseManager":
        if cls._instance is None:
            raise RuntimeError("DatabaseManager has not been initialised")
        return cls._instance

    @classmethod
    def is_initialised(cls) -> bool:
        return cls._instance is not None

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    async def shutdown(self) -> None:
        if self.supabase is not None:
            await self.supabase.aclose()
            self.supabase = None
            self.sensor_readings = None
            self.fire_stations = None
            self.devices = None
            self.fire_images = None
        DatabaseManager._instance = None
