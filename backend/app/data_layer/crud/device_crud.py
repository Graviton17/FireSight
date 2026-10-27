from datetime import UTC, datetime
from typing import Any, Dict, Optional

from app.data_layer.crud.base_crud import BaseCrud
from app.data_layer.data_classes.device import Device
from app.data_layer.supabase_client import SupabaseClient
from app.data_layer.tables_name_constant import TablesNameConstant


class DeviceCrud(BaseCrud):
    """CRUD operations for public.devices (primary key: device_id)."""

    def __init__(self, supabase: SupabaseClient):
        super().__init__(
            supabase=supabase,
            table_name=TablesNameConstant.DEVICES,
            model_class=Device,
        )

    async def get_by_device_id(self, device_id: str) -> Optional[Device]:
        response = (
            await self.supabase.table(self.table_name)
            .select("*")
            .eq("device_id", device_id)
            .limit(1)
            .execute()
        )
        if response.data:
            return self._row_to_model(response.data[0])
        return None

    async def upsert_device(self, device_id: str, data: Dict[str, Any]) -> Device:
        payload = {**data, "device_id": device_id, "updated_at": datetime.now(UTC).isoformat()}
        response = (
            await self.supabase.table(self.table_name)
            .upsert(payload, on_conflict="device_id")
            .execute()
        )
        if not response.data:
            raise Exception(f"Failed to upsert device '{device_id}': {response}")
        return self._row_to_model(response.data[0])
