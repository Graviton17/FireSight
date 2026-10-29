"""The in-memory event bus behind GET /api/v1/events."""

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.services.live_events import LiveEvents
from app.services.sensor_reading_service import SensorReadingService
from app.data_layer.data_classes.sensor_reading import SensorReading
from main import app


@pytest.fixture(autouse=True)
def fresh_bus(monkeypatch):
    monkeypatch.setattr(LiveEvents, "_queues", set())
    monkeypatch.setattr(LiveEvents, "_closed", False)


def test_subscribers_get_published_events():
    async def run():
        async with LiveEvents.subscribe() as a, LiveEvents.subscribe() as b:
            LiveEvents.publish("alert", "esp32-fire-01")
            return a.get_nowait(), b.get_nowait()

    assert asyncio.run(run()) == ({"kind": "alert", "device_id": "esp32-fire-01"},) * 2
    assert LiveEvents._queues == set()  # unsubscribed on exit


def test_close_all_ends_streams():
    async def run():
        async with LiveEvents.subscribe() as queue:
            LiveEvents.close_all()
            return await queue.get()

    assert asyncio.run(run()) is None


def test_stream_sends_events_then_stops_on_shutdown():
    async def run():
        from app.api.v1.event_routes import stream_events

        class _Request:
            async def is_disconnected(self):
                return False

        response = await stream_events(_Request())
        chunks = response.body_iterator
        assert (await anext(chunks)).startswith("retry:")
        LiveEvents.publish("reading", "esp32-fire-01")
        assert await anext(chunks) == 'data: {"kind": "reading", "device_id": "esp32-fire-01"}\n\n'
        LiveEvents.close_all()
        with pytest.raises(StopAsyncIteration):
            await anext(chunks)

    asyncio.run(run())


def test_posting_a_reading_publishes(monkeypatch):
    async def fake_record_reading(**kwargs):
        return SensorReading(id="r-1", created_at="2026-10-29T12:00:00+00:00", **kwargs)

    monkeypatch.setattr(SensorReadingService, "record_reading", staticmethod(fake_record_reading))
    published = []
    monkeypatch.setattr(LiveEvents, "publish", classmethod(lambda cls, kind, device_id: published.append((kind, device_id))))
    body = {"device_id": "esp32-fire-01", "smoke": 100, "flame": 4000, "temperature": 25.0, "fire": False}
    assert TestClient(app).post("/api/v1/sensor-data", json=body).status_code == 201
    assert published == [("reading", "esp32-fire-01")]
