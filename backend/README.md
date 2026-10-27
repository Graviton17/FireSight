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
supabase/migrations/        SQL for sensor_readings, fire_stations, devices
scripts/fire_stations/      Google Maps scrape + importer for Gujarat fire stations
tests/
```

## Setup

1. Run the files in `supabase/migrations/` in order in your Supabase project
   (SQL editor, or `supabase db push`).
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
| GET | `/api/v1/fire-stations?search=&page=&page_size=` | Station directory, alphabetical. |
| POST | `/api/v1/fire-stations` | Add a station by hand: `name`, `latitude`, `longitude`, optional `address`, `city`, `phone`, … |
| GET | `/api/v1/fire-stations/nearest?latitude=&longitude=&limit=3` | Closest stations to a point. |
| PUT | `/api/v1/devices/{device_id}` | Set where a device is installed: `latitude`, `longitude`, optional `name`, `address`. |
| GET | `/api/v1/devices/{device_id}/nearest-fire-stations?limit=3` | Closest stations to that device. |
| GET | `/health` | 503 until Supabase is connected. |

Test the POST by hand:

```bash
curl -X POST http://localhost:8000/api/v1/sensor-data \
  -H "Content-Type: application/json" \
  -d '{"device_id":"esp32-fire-01","smoke":1200,"flame":3900,"temperature":28.4,"fire":false}'
```

## Fire stations (Gujarat)

Stations come from a Google Maps scrape with
[gosom/google-maps-scraper](https://github.com/gosom/google-maps-scraper)
(runs in Docker), driven by `scripts/fire_stations/queries_gujarat.txt`: every
district HQ, major towns and industrial areas, and zone-level queries for
Ahmedabad, Surat, Vadodara and Rajkot.

```bash
./scripts/fire_stations/run_scraper.sh          # ~30-60 min, writes output/gujarat_fire_stations.csv
uv run python scripts/fire_stations/import_fire_stations.py \
  scripts/fire_stations/output/gujarat_fire_stations.csv --dry-run   # review output/cleaned_fire_stations.csv
uv run python scripts/fire_stations/import_fire_stations.py \
  scripts/fire_stations/output/gujarat_fire_stations.csv             # upsert into Supabase
```

The importer drops non-stations (extinguisher shops, safety consultants),
anything outside Gujarat and permanently closed places, and upserts on Google
`place_id`, so re-running after a new scrape updates rows instead of duplicating
them. Add anything the scrape missed with `POST /api/v1/fire-stations`.

**On a fire alarm:** register each device's location once
(`PUT /api/v1/devices/esp32-fire-01` with its lat/lng). When a reading arrives
with `fire: true`, the backend looks up the 3 nearest stations, logs the
closest one (name, phone, distance, Maps link), and returns them in the POST
response as `nearest_fire_stations`. The lookup uses a PostGIS index (no full
table scan); distances are straight-line, not road.

## Tests

```bash
.venv/bin/pytest
```

> No device auth yet: anyone on the network can POST readings.
