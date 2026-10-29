"""The PostgREST client retries read-only requests when Supabase drops a pooled connection."""

import asyncio

import httpx
import pytest

from app.data_layer.supabase_client import _RetryTransport


class _Flaky(httpx.AsyncBaseTransport):
    def __init__(self, failures: int):
        self.failures = failures
        self.calls = 0

    async def handle_async_request(self, request):
        self.calls += 1
        if self.calls <= self.failures:
            raise httpx.ReadError("connection closed", request=request)
        return httpx.Response(200, json=[{"ok": True}])


def _send(transport, method="GET"):
    async def go():
        async with httpx.AsyncClient(transport=transport, base_url="https://x.supabase.co") as client:
            return await client.request(method, "/rest/v1/fire_images")

    return asyncio.run(go())


def test_get_retried_after_dropped_connection():
    inner = _Flaky(failures=1)
    assert _send(_RetryTransport(inner)).status_code == 200
    assert inner.calls == 2


def test_gives_up_after_retries():
    inner = _Flaky(failures=5)
    with pytest.raises(httpx.ReadError):
        _send(_RetryTransport(inner))
    assert inner.calls == 3


def test_writes_not_retried():
    # A POST may have reached the database; repeating it could insert twice.
    inner = _Flaky(failures=1)
    with pytest.raises(httpx.ReadError):
        _send(_RetryTransport(inner), method="POST")
    assert inner.calls == 1
