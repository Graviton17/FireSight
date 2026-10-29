from typing import Any, Dict, List, Optional, Tuple

from postgrest.types import CountMethod

from app.data_layer.crud.base_crud import BaseCrud
from app.data_layer.data_classes.fire_station import FireStation, MapFireStation, NearbyFireStation
from app.data_layer.supabase_client import SupabaseClient
from app.data_layer.tables_name_constant import RpcFunctionsConstant, TablesNameConstant

_UPSERT_BATCH_SIZE = 200


class FireStationCrud(BaseCrud):
    """CRUD operations for public.fire_stations."""

    def __init__(self, supabase: SupabaseClient):
        super().__init__(
            supabase=supabase,
            table_name=TablesNameConstant.FIRE_STATIONS,
            model_class=FireStation,
        )

    async def upsert_by_place_id(self, rows: List[Dict[str, Any]]) -> int:
        """Insert or update scraped stations keyed on Google ``place_id``.

        Returns the number of rows written.
        """
        written = 0
        for start in range(0, len(rows), _UPSERT_BATCH_SIZE):
            batch = rows[start : start + _UPSERT_BATCH_SIZE]
            response = (
                await self.supabase.table(self.table_name)
                .upsert(batch, on_conflict="place_id")
                .execute()
            )
            written += len(response.data or [])
        return written

    async def list_stations(
        self,
        page: int = 1,
        page_size: int = 50,
        search: Optional[str] = None,
    ) -> Tuple[List[FireStation], int]:
        """Alphabetical; *search* matches name, city or address."""
        offset = (page - 1) * page_size
        query = self.supabase.table(self.table_name).select("*", count=CountMethod.exact)
        if search:
            # PostgREST or-filter syntax; strip characters that would break it.
            term = "".join(c for c in search if c not in ",()*%")
            query = query.or_(f"name.ilike.*{term}*,city.ilike.*{term}*,address.ilike.*{term}*")
        response = await query.order("name").range(offset, offset + page_size - 1).execute()
        return [self._row_to_model(r) for r in response.data], response.count or 0

    async def nearest(
        self, latitude: float, longitude: float, limit: int = 3
    ) -> List[NearbyFireStation]:
        response = await self.supabase.rpc(
            RpcFunctionsConstant.NEAREST_FIRE_STATIONS,
            {"p_latitude": latitude, "p_longitude": longitude, "p_limit": limit},
            get=True,
        ).execute()
        return [NearbyFireStation(**row) for row in response.data or []]

    async def in_bounds(
        self, min_lat: float, min_lng: float, max_lat: float, max_lng: float, limit: int
    ) -> List[MapFireStation]:
        response = await self.supabase.rpc(
            RpcFunctionsConstant.FIRE_STATIONS_IN_BOUNDS,
            {
                "p_min_lat": min_lat,
                "p_min_lng": min_lng,
                "p_max_lat": max_lat,
                "p_max_lng": max_lng,
                "p_limit": limit,
            },
            get=True,
        ).execute()
        return [MapFireStation(**row) for row in response.data or []]
