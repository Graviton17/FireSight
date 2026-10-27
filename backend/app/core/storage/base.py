"""Abstract storage-bucket interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class BaseStorageBucket(ABC):
    """Contract for a single Supabase Storage bucket.

    FireSight buckets are private, so reads go through short-lived signed URLs.
    """

    @property
    @abstractmethod
    def bucket_name(self) -> str:
        """Supabase storage bucket id."""

    @abstractmethod
    async def upload(
        self,
        *,
        object_path: str,
        file_content: bytes,
        content_type: str,
        upsert: bool = True,
    ) -> str:
        """Upload *file_content* and return its object path."""

    @abstractmethod
    async def delete(self, object_path: str) -> bool:
        """Delete an object. Returns True on success."""

    @abstractmethod
    async def signed_url(self, object_path: str, expires_in: int = 3600) -> Optional[str]:
        """Return a temporary signed URL for the object."""
