import asyncio
import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.services.live_events import LiveEvents

router = APIRouter(prefix="/events", tags=["Live events"])

# Keeps proxies (Vite, ngrok) from closing an idle stream, and notices closed tabs.
HEARTBEAT_SECONDS = 15


@router.get("")
async def stream_events(request: Request):
    """Server-Sent Events: ``{"kind": "reading" | "alert" | "image", "device_id"}``
    whenever a device's data changes. The browser refetches what it shows."""

    async def stream():
        async with LiveEvents.subscribe() as queue:
            yield "retry: 1000\n\n"  # reconnect after 1 s if the stream drops
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), HEARTBEAT_SECONDS)
                except TimeoutError:
                    if await request.is_disconnected():
                        return
                    yield ": ping\n\n"
                    continue
                if event is None:  # server stopping
                    return
                yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
