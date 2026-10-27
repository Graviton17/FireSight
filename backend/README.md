# FireSight Backend

FastAPI service that receives readings from the ESP32 fire node and stores them
in Supabase. Same layering as grava:

```
main.py                     app + lifespan (Supabase init)
app/
  static_memory_cache.py    config.json loader
  telemetries/logger.py     structlog setup
  core/errors/              {"error": {code, message}} envelope
  api/v1/
    router.py               aggregates routers
    sensor_routes.py        /api/v1/sensor-data endpoints
    schemas/                Pydantic request/response models
  services/                 business logic (SensorReadingService)
  data_layer/
    database_manager.py     singleton holding Supabase + CRUD instances
    crud/                   BaseCrud + SensorReadingCrud
    data_classes/           one dataclass per table
supabase/migrations/        SQL for the sensor_readings table
tests/
```

## Setup

1. Run `supabase/migrations/20261027120000_create_sensor_readings.sql` in your
   Supabase project (SQL editor, or `supabase db push`).
2. `cp config.json.example config.json` and fill in the Supabase URL, the
   service-role key.
3. Install and run (with uv: `uv sync && uv run python main.py`), or with pip:

   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -e . pytest
   .venv/bin/python main.py
   ```

   The server listens on `0.0.0.0:8000`, so the ESP32 can reach it on your LAN IP.

## Endpoints

| Method | Path | Notes |
| --- | --- | --- |
| POST | `/api/v1/sensor-data` | Body: `device_id`, `smoke`, `flame`, `temperature` (nullable), `fire`. Returns 201. |
| GET | `/api/v1/sensor-data/{device_id}/latest` | Latest reading, 404 if none. |
| GET | `/api/v1/sensor-data/{device_id}?page=&page_size=` | History, newest first. |
| GET | `/health` | 503 until Supabase is connected. |

Test the POST by hand:

```bash
curl -X POST http://localhost:8000/api/v1/sensor-data \
  -H "Content-Type: application/json" \
  -d '{"device_id":"esp32-fire-01","smoke":1200,"flame":3900,"temperature":28.4,"fire":false}'
```

## Tests

```bash
.venv/bin/pytest
```

> No device auth yet: anyone on the network can POST readings.
