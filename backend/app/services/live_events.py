import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator, Literal, Optional, Set, TypedDict

import uvicorn

# reading : a device posted a reading            -> live values
# alert   : an incident started or was resolved  -> triggers, map, station
# image   : a fire snapshot and its verdict saved -> triggers
EventKind = Literal["reading", "alert", "image"]


class LiveEvent(TypedDict):
    kind: EventKind
    device_id: str


class LiveEvents:
    """Tells open browsers that something changed, so they refetch right away
    instead of waiting for their next poll (GET /api/v1/events).

    In memory: one backend process, so every publisher and subscriber is here.
    Events only say what changed; the data still comes from the normal routes.
    """

    _queues: Set["asyncio.Queue[Optional[LiveEvent]]"] = set()
    _closed = False

    @classmethod
    def publish(cls, kind: EventKind, device_id: str) -> None:
        event: LiveEvent = {"kind": kind, "device_id": device_id}
        for queue in list(cls._queues):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass  # a stuck browser; it still polls

    @classmethod
    @asynccontextmanager
    async def subscribe(cls) -> AsyncIterator["asyncio.Queue[Optional[LiveEvent]]"]:
        """Yields a queue of events; ``None`` in it means the server is stopping."""
        queue: "asyncio.Queue[Optional[LiveEvent]]" = asyncio.Queue(maxsize=256)
        if cls._closed:
            queue.put_nowait(None)
        cls._queues.add(queue)
        try:
            yield queue
        finally:
            cls._queues.discard(queue)

    @classmethod
    def close_all(cls) -> None:
        cls._closed = True
        for queue in list(cls._queues):
            try:
                queue.put_nowait(None)
            except asyncio.QueueFull:
                queue.get_nowait()
                queue.put_nowait(None)


def install_shutdown_hook() -> None:
    """uvicorn waits for open responses before it stops, and an event stream
    never ends on its own: end the streams as soon as shutdown starts."""
    original = uvicorn.Server.handle_exit
    if getattr(original, "_closes_live_events", False):
        return

    def handle_exit(self, sig, frame):
        LiveEvents.close_all()
        original(self, sig, frame)

    handle_exit._closes_live_events = True  # type: ignore[attr-defined]
    uvicorn.Server.handle_exit = handle_exit  # type: ignore[method-assign]
