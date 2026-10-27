# FireSight Backend

FastAPI service that receives readings from the ESP32 fire node and stores them
in Supabase. Same layering as grava:

```
main.py                     app + lifespan (Supabase init)
app/
  static_memory_cache.py    config.json loader
  telemetries/logger.py     structlog setup
  core/errors/              {"error": {code, message}} envelope
  core/camera/              IP Webcam (Android) snapshot client
  core/storage/             fire-images bucket adapter
  api/v1/
    router.py               aggregates routers
    sensor_routes.py        /api/v1/sensor-data endpoints
    schemas/                Pydantic request/response models
  services/                 SensorReadingService, FireCaptureService
  data_layer/
    database_manager.py     singleton holding Supabase + CRUD instances
    crud/                   BaseCrud + SensorReadingCrud
    data_classes/           one dataclass per table
supabase/migrations/        sensor_readings, fire_images (+ bucket), fire_stations, devices
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

## Phone camera (fire snapshots)

1. Install **IP Webcam** on the Android phone, tap **Start server**, and note the
   address it shows (e.g. `http://192.168.1.50:8080`). The phone must be on the
   same WiFi as the backend.
2. Check it works: open `http://<phone-ip>:8080/shot.jpg` in a browser.
3. Add to `config.json`:

   ```json
   "camera": {
     "base_url": "http://192.168.1.50:8080",
     "snapshot_path": "/shot.jpg",
     "username": "",
     "password": "",
     "timeout_seconds": 10,
     "capture_interval_seconds": 10
   }
   ```

   - `snapshot_path`: `/shot.jpg` = current video frame (fast); `/photo.jpg` =
     full-resolution photo with autofocus (slower).
   - `username`/`password`: only if you set a login in IP Webcam.
   - `capture_interval_seconds`: while the fire continues the ESP32 posts every
     5 s; this caps captures to one per device per interval.

   **Changing the IP on the fly:** the `camera` section is re-read whenever
   `config.json` is saved, so just edit `base_url` (or any camera setting) and
   save. No restart needed; the next fire capture uses the new value. (If
   `FIRESIGHT_CAMERA_URL` is set in the environment it always wins.)

When a POST has `"fire": true`, the backend replies immediately with
`"image_capture_scheduled": true`, then grabs the snapshot in the background,
uploads it to `fire-images/{device_id}/{date}/{reading_id}.jpg`, and inserts a
row in `fire_images` (`reading_id`, `device_id`, `bucket`, `storage_path`,
`content_type`, `size_bytes`, `captured_at`, all NOT NULL; one image per
reading). GET endpoints return it as `image` on the reading, with a signed
`url` (valid 1 hour). If the phone is unreachable the error is logged and the next fire
reading retries.

## Endpoints

| Method | Path | Notes |
| --- | --- | --- |
| POST | `/api/v1/sensor-data` | Body: `device_id`, `smoke`, `flame`, `temperature` (nullable), `fire`. Returns 201 with the reading + `image_capture_scheduled` + `nearest_fire_stations` (filled when `fire` is true). |
| GET | `/api/v1/sensor-data/{device_id}/latest` | Latest reading (with `image` if one was captured), 404 if none. |
| GET | `/api/v1/sensor-data/{device_id}/images?page=&page_size=` | Fire snapshots, newest first, with signed URLs. |
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
