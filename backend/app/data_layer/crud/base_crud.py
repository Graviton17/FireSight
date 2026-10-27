"""Generic async CRUD base class for Supabase PostgREST tables."""

import json
from dataclasses import asdict, fields, is_dataclass
from datetime import UTC, datetime
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple, cast

from postgrest.types import CountMethod
from supabase.client import AsyncClient

from app.data_layer.supabase_client import SupabaseClient

# Column names whose string values should be auto-parsed as JSON dicts/lists.
_DEFAULT_JSON_COLUMNS: FrozenSet[str] = frozenset({"metadata", "extra"})


class BaseCrud:
    """Async CRUD base providing standard create / read / update / delete.

    Parameters
    ----------
    supabase:
        An initialised ``SupabaseClient`` instance.
    table_name:
        The Supabase/PostgREST table to operate on.
    model_class:
        A ``@dataclass`` whose fields map to table columns. Rows returned
        from the database are converted to instances of this class.
    json_columns:
        Optional extra column names that should be auto-parsed from JSON
        strings when mapping rows.
    """

    def __init__(
        self,
        supabase: SupabaseClient,
        table_name: str,
        model_class: type,
        json_columns: Optional[Set[str]] = None,
    ):
        self.supabase: AsyncClient = supabase.get_client()
        self.table_name: str = table_name
        self.model_class: type = model_class
        self._json_columns: FrozenSet[str] = (
            _DEFAULT_JSON_COLUMNS | frozenset(json_columns)
            if json_columns
            else _DEFAULT_JSON_COLUMNS
        )

    # ------------------------------------------------------------------
    # Row ↔ Model mapping
    # ------------------------------------------------------------------

    def _row_to_model(self, db_data: Any) -> Any:
        """Map a DB row dict to a *model_class* instance.

        * Extra columns not present on the dataclass are silently ignored.
        * String values in ``_json_columns`` are auto-parsed to dicts/lists.
        """
        if not is_dataclass(self.model_class):
            return self.model_class(**db_data)

        valid_fields = {f.name for f in fields(self.model_class)}
        filtered_data = {k: v for k, v in db_data.items() if k in valid_fields}

        for col in self._json_columns:
            if col in filtered_data and isinstance(filtered_data[col], str):
                try:
                    filtered_data[col] = json.loads(filtered_data[col])
                except (json.JSONDecodeError, TypeError):
                    pass

        return self.model_class(**filtered_data)

    # ------------------------------------------------------------------
    # CRUD operations
    # ------------------------------------------------------------------

    async def create(self, data: Any) -> Any:
        """Insert a new row and return the created model instance.

        *data* can be a ``dict`` or a dataclass instance (will be converted).
        """
        if is_dataclass(data) and not isinstance(data, type):
            payload: Dict[str, Any] = asdict(data)
        else:
            payload = cast(Dict[str, Any], data)

        response = await self.supabase.table(self.table_name).insert(payload).execute()

        if not response.data:
            raise Exception(f"Failed to create record in '{self.table_name}': {response}")

        return self._row_to_model(response.data[0])

    async def get_by_id(self, id: str) -> Optional[Any]:
        """Fetch a single row by its ``id`` column."""
        response = (
            await self.supabase.table(self.table_name)
            .select("*")
            .eq("id", id)
            .execute()
        )
        if response.data:
            return self._row_to_model(response.data[0])
        return None

    async def get_by_ids(self, ids: List[str]) -> List[Any]:
        """Batch-fetch rows by ``id`` — one query instead of N."""
        if not ids:
            return []
        response = (
            await self.supabase.table(self.table_name)
            .select("*")
            .in_("id", ids)
            .execute()
        )
        return [self._row_to_model(item) for item in response.data]

    async def get_all(self) -> List[Any]:
        """Return every row in the table."""
        response = await self.supabase.table(self.table_name).select("*").execute()
        return [self._row_to_model(item) for item in response.data]

    async def update(self, id: str, data: Dict[str, Any]) -> Optional[Any]:
        """Update a row by ``id`` and return the updated model."""
        if is_dataclass(self.model_class):
            model_field_names = {f.name for f in fields(self.model_class)}
            if "updated_at" in model_field_names:
                data.setdefault("updated_at", datetime.now(UTC).isoformat())

        response = (
            await self.supabase.table(self.table_name)
            .update(data)
            .eq("id", id)
            .execute()
        )
        if response.data:
            return self._row_to_model(response.data[0])
        return None

    async def delete(self, id: str) -> bool:
        """Delete a row by ``id``. Returns ``True`` if a row was removed."""
        response = (
            await self.supabase.table(self.table_name)
            .delete()
            .eq("id", id)
            .execute()
        )
        return bool(response.data)

    # ------------------------------------------------------------------
    # Filtering & search
    # ------------------------------------------------------------------

    async def filter_by(self, **filters: Any) -> List[Any]:
        """Return rows matching all non-None keyword filters (AND logic)."""
        query = self.supabase.table(self.table_name).select("*")
        for key, value in filters.items():
            if value is not None:
                query = query.eq(key, value)
        response = await query.execute()
        return [self._row_to_model(item) for item in response.data]

    async def search(self, column: str, search_term: str) -> List[Any]:
        """Case-insensitive LIKE search on *column*."""
        response = (
            await self.supabase.table(self.table_name)
            .select("*")
            .ilike(column, f"%{search_term}%")
            .execute()
        )
        return [self._row_to_model(item) for item in response.data]

    # ------------------------------------------------------------------
    # Pagination & counting
    # ------------------------------------------------------------------

    async def paginate(
        self,
        page: int = 1,
        page_size: int = 20,
        order_by: Optional[str] = None,
        descending: bool = False,
        **filters: Any,
    ) -> Tuple[List[Any], int]:
        """Return a ``(items, total_count)`` tuple with offset-based pagination."""
        offset = (page - 1) * page_size

        query = self.supabase.table(self.table_name).select("*", count=CountMethod.exact)
        for key, value in filters.items():
            if value is not None:
                query = query.eq(key, value)
        if order_by:
            query = query.order(order_by, desc=descending)
        response = await query.range(offset, offset + page_size - 1).execute()

        items = [self._row_to_model(item) for item in response.data]
        return items, response.count or 0

    async def count(self, **filters: Any) -> int:
        """Return the count of rows matching *filters*."""
        query = self.supabase.table(self.table_name).select("id", count=CountMethod.exact)
        for key, value in filters.items():
            if value is not None:
                query = query.eq(key, value)
        response = await query.execute()
        return response.count or 0
