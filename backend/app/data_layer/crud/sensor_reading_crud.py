from typing import List, Optional, Tuple

from app.data_layer.crud.base_crud import BaseCrud
from app.data_layer.data_classes.sensor_reading import SensorReading
from app.data_layer.supabase_client import SupabaseClient
from app.data_layer.tables_name_constant import TablesNameConstant


class SensorReadingCrud(BaseCrud):
    """CRUD operations for public.sensor_readings."""

    def __init__(self, supabase: SupabaseClient):
        super().__init__(
            supabase=supabase,
            table_name=TablesNameConstant.SENSOR_READINGS,
            model_class=SensorReading,
        )

    async def create_reading(
        self,
        device_id: str,
        smoke: int,
        flame: int,
        temperature: Optional[float],
        fire: bool,
    ) -> SensorReading:
        return await self.create(
            {
                "device_id": device_id,
                "smoke": smoke,
                "flame": flame,
                "temperature": temperature,
                "fire": fire,
            }
        )

    async def get_latest(self, device_id: str) -> Optional[SensorReading]:
        response = (
            await self.supabase.table(self.table_name)
            .select("*")
            .eq("device_id", device_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if response.data:
            return self._row_to_model(response.data[0])
        return None

    async def list_for_device(
        self,
        device_id: str,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[SensorReading], int]:
        """Newest first."""
        return await self.paginate(
            page=page,
            page_size=page_size,
            order_by="created_at",
            descending=True,
            device_id=device_id,
        )
