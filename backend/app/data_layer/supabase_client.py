from typing import Any, Dict, List, Optional

from httpx import AsyncClient as HttpxAsyncClient
from httpx import Limits, Timeout
from supabase.client import AsyncClient, acreate_client

from app.telemetries.logger import logger

# PostgREST defaults to http2=True which caps concurrent streams; use HTTP/1.1.
_SUPABASE_HTTP_LIMITS = Limits(max_connections=50, max_keepalive_connections=20)
_SUPABASE_HTTP_TIMEOUT = Timeout(30.0)


def _build_postgrest_http_client(
    base_url: str, headers: Dict[str, str]
) -> HttpxAsyncClient:
    """Build an HTTP/1.1 client dedicated to PostgREST calls."""
    return HttpxAsyncClient(
        base_url=base_url,
        headers=headers,
        http2=False,
        follow_redirects=True,
        limits=_SUPABASE_HTTP_LIMITS,
        timeout=_SUPABASE_HTTP_TIMEOUT,
    )


def _patch_postgrest_http1(async_client: AsyncClient) -> tuple:
    """Give PostgREST its own HTTP/1.1 client so base_url is not clobbered."""
    pg = async_client.postgrest
    old_session = pg.session
    base_url = str(old_session.base_url).rstrip("/")
    headers = dict(old_session.headers)
    new_session = _build_postgrest_http_client(base_url, headers)
    pg.session = new_session
    return old_session, new_session


class SupabaseClient:
    """Thin async wrapper around ``supabase-py`` AsyncClient.

    Domain CRUD uses the query builder via :meth:`table`.
    """

    def __init__(
        self,
        async_client: AsyncClient,
        postgrest_http_clients: List[HttpxAsyncClient],
        supabase_url: str,
    ):
        self.async_client = async_client
        self._postgrest_http_clients = postgrest_http_clients
        self.supabase_url = supabase_url.rstrip("/")

    @classmethod
    async def create(cls, supabase_url: str, supabase_key: str) -> "SupabaseClient":
        if not supabase_url or not supabase_key:
            raise ValueError("Supabase URL and Key must be provided")

        async_client: AsyncClient = await acreate_client(supabase_url, supabase_key)
        old_session, new_session = _patch_postgrest_http1(async_client)
        await old_session.aclose()
        return cls(async_client, [new_session], supabase_url)

    async def aclose(self) -> None:
        for client in self._postgrest_http_clients:
            await client.aclose()
        self._postgrest_http_clients.clear()

    def get_client(self) -> AsyncClient:
        return self.async_client

    def table(self, table_name: str):
        """Expose the underlying async_client.table() for builder-style queries."""
        return self.async_client.table(table_name)

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------

    async def upload_file(
        self,
        bucket_name: str,
        file_path: str,
        file_content: bytes,
        content_type: str = "application/octet-stream",
        upsert: bool = False,
    ) -> bool:
        """Upload a file to Supabase Storage."""
        try:
            await self.async_client.storage.from_(bucket_name).upload(
                path=file_path,
                file=file_content,
                file_options={
                    "content-type": content_type,
                    "upsert": "true" if upsert else "false",
                },
            )
            return True
        except Exception as e:
            logger.error("Error uploading file", bucket=bucket_name, path=file_path, exc_info=e)
            return False

    async def delete_files(self, bucket_name: str, file_paths: List[str]) -> bool:
        """Delete one or more files from Supabase Storage."""
        if not file_paths:
            return True
        try:
            await self.async_client.storage.from_(bucket_name).remove(file_paths)
            return True
        except Exception as e:
            logger.error("Error deleting files", bucket=bucket_name, exc_info=e)
            return False

    async def create_signed_url(
        self, bucket_name: str, file_path: str, expires_in: int
    ) -> Optional[str]:
        """Return a temporary signed URL for an object in a private bucket."""
        try:
            result = await self.async_client.storage.from_(bucket_name).create_signed_url(
                file_path,
                expires_in,
            )
            if isinstance(result, dict):
                return (
                    result.get("signedURL")
                    or result.get("signedUrl")
                    or result.get("signed_url")
                )
            return getattr(result, "signed_url", None) or getattr(result, "signedURL", None)
        except Exception as e:
            logger.error("Error creating signed URL", bucket=bucket_name, path=file_path, exc_info=e)
            return None

    # ------------------------------------------------------------------
    # RPC
    # ------------------------------------------------------------------

    async def call_rpc_function(
        self, function_name: str, params: Dict[str, Any]
    ) -> Optional[Any]:
        """Call a PostgreSQL RPC function. Returns ``None`` on error."""
        try:
            response = await self.async_client.rpc(function_name, params).execute()
            return response.data if response.data is not None else []
        except Exception as e:
            logger.error("Error calling RPC", function=function_name, exc_info=e)
            return None
