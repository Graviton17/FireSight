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
supabase/migrations/        sensor_readings, fire_images, fire_detections; fire-images bucket
models/                     local model weights (gitignored, see 'Fire model')
tests/
```

## Setup

1. Run both files in `supabase/migrations/` in order in your Supabase project
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
| POST | `/api/v1/sensor-data` | Body: `device_id`, `smoke`, `flame`, `temperature` (nullable), `fire`. Returns 201 with the reading, `buzz` and `verification`. |
| GET | `/api/v1/sensor-data/{device_id}/latest` | Latest reading (with `image` if one was captured), 404 if none. |
| GET | `/api/v1/sensor-data/{device_id}/images?page=&page_size=` | Fire snapshots, newest first, with signed URLs. |
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
