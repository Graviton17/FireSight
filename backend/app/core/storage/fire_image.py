"""Fire-image storage adapter for the private ``fire-images`` bucket.

Object layout: ``fire-images/{device_id}/{YYYY-MM-DD}/{reading_id}.jpg``. The
object path (without the bucket) is stored on ``fire_images.storage_path``
and signed on read.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from app.core.storage.base import BaseStorageBucket
from app.core.storage.constants import FireImageLimits, StorageBuckets
from app.data_layer.database_manager import DatabaseManager
from app.data_layer.supabase_client import SupabaseClient


class FireImageStorage(BaseStorageBucket):
    """Upload / delete / sign images captured when a device reports fire."""

    @property
    def bucket_name(self) -> str:
        return StorageBuckets.FIRE_IMAGES

    def _client(self) -> SupabaseClient:
        return DatabaseManager.get_instance().get_supabase_client()

    @staticmethod
    def object_path_for(device_id: str, reading_id: str, captured_at: datetime) -> str:
        return f"{device_id}/{captured_at.strftime('%Y-%m-%d')}/{reading_id}.jpg"

    # ------------------------------------------------------------------
    # BaseStorageBucket
    # ------------------------------------------------------------------

    async def upload(
        self,
        *,
        object_path: str,
        file_content: bytes,
        content_type: str = FireImageLimits.CONTENT_TYPE,
        upsert: bool = True,
    ) -> str:
        ok = await self._client().upload_file(
            bucket_name=self.bucket_name,
            file_path=object_path,
            file_content=file_content,
            content_type=content_type,
            upsert=upsert,
        )
        if not ok:
            raise RuntimeError(f"Failed to upload fire image to {self.bucket_name}/{object_path}")
        return object_path

    async def delete(self, object_path: str) -> bool:
        return await self._client().delete_files(self.bucket_name, [object_path])

    async def signed_url(
        self, object_path: str, expires_in: int = FireImageLimits.SIGNED_URL_TTL_SECONDS
    ) -> Optional[str]:
        return await self._client().create_signed_url(self.bucket_name, object_path, expires_in)
