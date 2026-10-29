from datetime import UTC, datetime
from typing import Any, Dict, List, Optional

from app.data_layer.crud.base_crud import BaseCrud
from app.data_layer.data_classes.device import Device, MapDevice
from app.data_layer.supabase_client import SupabaseClient
from app.data_layer.tables_name_constant import RpcFunctionsConstant, TablesNameConstant


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

    async def get_by_device_ids(self, device_ids: List[str]) -> Dict[str, Device]:
        """device_id -> device, one query."""
        if not device_ids:
            return {}
        response = (
            await self.supabase.table(self.table_name)
            .select("*")
            .in_("device_id", device_ids)
            .execute()
        )
        devices = [self._row_to_model(row) for row in response.data]
        return {device.device_id: device for device in devices}

    async def in_bounds(
        self, min_lat: float, min_lng: float, max_lat: float, max_lng: float, limit: int
    ) -> List[MapDevice]:
        response = await self.supabase.rpc(
            RpcFunctionsConstant.DEVICES_IN_BOUNDS,
            {
                "p_min_lat": min_lat,
                "p_min_lng": min_lng,
                "p_max_lat": max_lat,
                "p_max_lng": max_lng,
                "p_limit": limit,
            },
        ).execute()
        return [MapDevice(**row) for row in response.data or []]
