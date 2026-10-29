from datetime import UTC, datetime
from typing import Any, Dict, List, Optional, Tuple

from app.data_layer.crud.base_crud import BaseCrud
from app.data_layer.data_classes.fire_alert import FireAlert
from app.data_layer.supabase_client import SupabaseClient
from app.data_layer.tables_name_constant import TablesNameConstant


class FireAlertCrud(BaseCrud):
    """CRUD operations for public.fire_alerts."""

    def __init__(self, supabase: SupabaseClient):
        super().__init__(
            supabase=supabase,
            table_name=TablesNameConstant.FIRE_ALERTS,
            model_class=FireAlert,
        )

    async def create_alert(self, data: Dict[str, Any]) -> FireAlert:
        return await self.create(data)

    async def list_for_station(
        self, fire_station_id: str, page: int = 1, page_size: int = 20
    ) -> Tuple[List[FireAlert], int]:
        """Newest first."""
        return await self.paginate(
            page=page,
            page_size=page_size,
            order_by="created_at",
            descending=True,
            fire_station_id=fire_station_id,
        )

    async def list_for_device(
        self, device_id: str, page: int = 1, page_size: int = 20
    ) -> Tuple[List[FireAlert], int]:
        """Newest first."""
        return await self.paginate(
            page=page,
            page_size=page_size,
            order_by="created_at",
            descending=True,
            device_id=device_id,
        )

    async def latest_for_device(self, device_id: str) -> Optional[FireAlert]:
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

    async def live_for_device(self, device_id: str) -> Optional[FireAlert]:
        """The device's unresolved incident, if any."""
        response = (
            await self.supabase.table(self.table_name)
            .select("*")
            .eq("device_id", device_id)
            .is_("resolved_at", "null")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if response.data:
            return self._row_to_model(response.data[0])
        return None

    async def resolve_live(self, device_id: str) -> List[FireAlert]:
        """Close every live incident of the device. Returns the closed rows."""
        response = (
            await self.supabase.table(self.table_name)
            .update({"resolved_at": datetime.now(UTC).isoformat()})
            .eq("device_id", device_id)
            .is_("resolved_at", "null")
            .execute()
        )
        return [self._row_to_model(row) for row in response.data]
