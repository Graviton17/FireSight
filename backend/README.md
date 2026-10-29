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
  core/detection/           fire image classifier (torch/transformers)
  api/v1/
    router.py               aggregates routers
    sensor_routes.py        /api/v1/sensor-data endpoints
    schemas/                Pydantic request/response models
  services/                 SensorReadingService, FireCaptureService, FireVerificationService
  data_layer/
    database_manager.py     singleton holding Supabase + CRUD instances
    crud/                   BaseCrud + SensorReadingCrud
    data_classes/           one dataclass per table
supabase/migrations/        sensor_readings, fire_images, fire_detections, fire_stations, devices, fire_alerts; fire-images bucket
scripts/fire_stations/      Google Maps scrape + importer for Gujarat fire stations
models/                     local model weights (gitignored, see 'Fire model')
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
     "timeout_seconds": 3
   }
   ```

   - `snapshot_path`: `/shot.jpg` = current video frame (fast); `/photo.jpg` =
     full-resolution photo with autofocus (slower).
   - `username`/`password`: only if you set a login in IP Webcam.

   **Changing the IP on the fly:** the `camera` section is re-read whenever
   `config.json` is saved, so just edit `base_url` (or any camera setting) and
   save. No restart needed; the next fire capture uses the new value. (If
   `FIRESIGHT_CAMERA_URL` is set in the environment it always wins.)

## Fire model (second verification)

The sensors are the first check. When the ESP32 reports `"fire": true`, the
backend grabs a phone snapshot, runs the image classifier
[`prithivMLmods/Fire-Detection-Siglip2`](https://huggingface.co/prithivMLmods/Fire-Detection-Siglip2)
(labels `fire`, `normal`, `smoke`; 99.4% accuracy on its own test set), and
answers the POST with `buzz`. The model runs locally on CPU, well inside the
ESP32's 5 s timeout.

**Download the model once** (~370 MB, into `models/`, which is gitignored):

```bash
D=models/Fire-Detection-Siglip2; mkdir -p $D
B=https://huggingface.co/prithivMLmods/Fire-Detection-Siglip2/resolve/main
for f in config.json preprocessor_config.json model.safetensors; do curl -L -o $D/$f $B/$f; done
```

It is loaded from that folder at startup (`Fire model loaded` in the log); the
server never downloads anything at runtime.

```json
"detection": {
  "enabled": true,
  "model_path": "models/Fire-Detection-Siglip2",
  "fire_labels": ["fire", "smoke"],
  "threshold": 0.7,
  "timeout_seconds": 4,
  "device": "cpu"
}
```

- `fire_score` = sum of the `fire_labels` probabilities; fire is confirmed when
  `fire_score >= threshold`. `threshold` and `timeout_seconds` change live when
  config.json is saved.
- `timeout_seconds`: budget for camera + model. Keep it under the ESP32's 5 s.

| `verification.status` | When | `buzz` |
| --- | --- | --- |
| `not_needed` | sensors say no fire | `false` |
| `confirmed` | model sees fire/smoke | `true` |
| `rejected` | model sees no fire | `false` |
| `unavailable` | camera down, model not loaded/failed, or timeout | `true` (fail-safe) |

After the response, the snapshot goes to the `fire-images` bucket +
`fire_images` row, and the verdict to `fire_detections` (label, fire_score,
threshold, all scores, inference time). GET endpoints return the image with a
signed `url` and its `detection`.

## Endpoints

| Method | Path | Notes |
| --- | --- | --- |
| POST | `/api/v1/sensor-data` | Body: `device_id`, `smoke`, `flame`, `temperature` (nullable), `fire`. Returns 201 with the reading, `buzz`, `verification` and `nearest_fire_stations` (filled when `buzz` is true). |
| GET | `/api/v1/sensor-data/{device_id}/latest` | Latest reading (with `image` if one was captured), 404 if none. |
| GET | `/api/v1/sensor-data/{device_id}/images?page=&page_size=` | Fire snapshots, newest first, with signed URLs. |
| GET | `/api/v1/sensor-data/{device_id}?page=&page_size=` | History, newest first. |
| GET | `/api/v1/fire-stations?search=&page=&page_size=` | Station directory, alphabetical. |
| POST | `/api/v1/fire-stations` | Add a station by hand: `name`, `latitude`, `longitude`, optional `address`, `city`, `phone`, … |
| GET | `/api/v1/fire-stations/nearest?latitude=&longitude=&limit=3` | Closest stations to a point. |
| GET | `/api/v1/fire-stations/in-bounds?min_lat=&min_lng=&max_lat=&max_lng=&limit=500` | Stations in a map viewport, with `alert_count` and `last_alert_at`. `truncated` is true when `limit` was hit. |
| GET | `/api/v1/fire-stations/{id}` | One station. |
| GET | `/api/v1/fire-stations/{id}/alerts?page=&page_size=` | Alarms that called this station, newest first, with `device_name`. |
| PUT | `/api/v1/devices/{device_id}` | Set where a device is installed: `latitude`, `longitude`, optional `name`, `address`. |
| GET | `/api/v1/devices/{device_id}/nearest-fire-stations?limit=3` | Closest stations to that device. |
| GET | `/api/v1/devices/in-bounds?min_lat=&min_lng=&max_lat=&max_lng=&limit=500` | Devices in a map viewport, each with its latest reading (`last_*`) and alert count. |
| GET | `/api/v1/devices/{device_id}` | One device's location. |
| GET | `/api/v1/devices/{device_id}/alerts?page=&page_size=` | This device's alarms and the station each one called, newest first. |
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

**Device location:** comes from the IP Webcam phone's GPS (the phone sits next
to the ESP32). Tick **Get location** on the phone's Sensors page
(`http://<phone-ip>:8080/sensors.html`); startup logs `Phone location OK` with a
Maps link. Fixes worse than `camera.location_max_accuracy_m` (50 m) are ignored.
A location pinned by hand with `PUT /api/v1/devices/{device_id}` always wins.
With several devices, set `camera.device_id` so only the one next to the phone
uses its GPS.

**Device location:** comes from the IP Webcam phone's GPS (the phone sits next
to the ESP32). Tick **Get location** on the phone's Sensors page
(`http://<phone-ip>:8080/sensors.html`); startup logs `Phone location OK` with a
Maps link. Fixes worse than `camera.location_max_accuracy_m` (50 m) are ignored.
A location pinned by hand with `PUT /api/v1/devices/{device_id}` always wins.
With several devices, set `camera.device_id` so only the one next to the phone
uses its GPS.

**On a fire alarm:** the station lookup runs alongside the image verification.
If the alarm buzzes, the backend logs the fire's location and the nearest
station (name, phone, distance, Maps link) and returns the 3 nearest in the
POST response as `nearest_fire_stations`. The lookup uses a PostGIS index (no
full table scan); distances are straight-line, not road. After the response,
a `fire_alerts` row records that the device called its nearest station (time,
distance, camera verdict, sensor values); the map's popups read these.

## Tests

```bash
.venv/bin/pytest
```

> No device auth yet: anyone on the network can POST readings.
