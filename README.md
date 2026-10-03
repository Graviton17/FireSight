# FireSight

**A self-hosted IoT fire-alarm prototype with multi-sensor triggering and camera-based verification.**

FireSight combines an ESP32 sensing node, a FastAPI decision service, an Android IP camera, and a React/Vite dashboard. It uses smoke/gas, temperature, humidity, and multi-frame visual evidence to reduce nuisance alarms from steam, cooking smoke, and incense while keeping a sensor-only fallback path.

> [!WARNING]
> FireSight is an educational prototype, not a certified fire-safety product. Do not use it as a replacement for approved smoke detectors or to contact emergency services automatically.

## Why FireSight

- **Multiple signals, one decision:** MQ-2 gas/smoke trends, temperature, humidity, and camera evidence are combined by an explainable rule-based decision engine.
- **Fail-safe escalation:** camera or network failure cannot indefinitely suppress an alarm; the ESP32 also has a local fallback alarm path.
- **Auditable incidents:** telemetry, state changes, and alarm evidence are designed to be stored locally for review.
- **One repository, three runtimes:** backend, web dashboard, and ESP32 firmware evolve together while sharing versioned API contracts.

## Architecture

```text
ESP32 node                    FastAPI backend                   Browser dashboard
MQ-2 + DHT11 + buzzer   ->    telemetry + decision engine  ->   live state and history
      ^                         camera + detector                  controls
      |                         SQLite + evidence frames           |
      +--------------------- buzzer command <----------------------+
```

The ESP32 posts a heartbeat every two seconds and receives the current buzzer command in the response. When readings are suspicious, the backend starts camera verification. Camera evidence can confirm an alarm or postpone it, but it cannot cancel safety escalation rules.

## Repository layout

```text
apps/
  backend/          FastAPI API, decision-service layers, and tests
  frontend/         React and Vite monitoring dashboard
  firmware/esp32/   PlatformIO and Arduino C++ application
packages/
  contracts/        JSON Schemas shared by backend, frontend, and firmware
docs/               Architecture and development documentation
infra/              Docker and deployment assets
tools/              Local simulators and developer utilities
```

See [the repository-layout guide](docs/repository-layout.md) for module boundaries and ownership rules.

## Quick start

### Prerequisites

- Python 3.11 or later
- Node.js 20.19+ or 22.12+ for the Vite dashboard
- PlatformIO Core for ESP32 builds

### 1. Run the backend

```bash
python -m venv .venv
source .venv/bin/activate
make api-install
cp apps/backend/.env.example apps/backend/.env
make api-run
```

The API starts on `http://localhost:8000`. Open `http://localhost:8000/docs` to explore the generated API documentation.

### 2. Run the dashboard

```bash
cd apps/frontend
npm install
npm run dev
```

The dashboard is served at `http://localhost:5173` by default. Configure its backend address as described in the [frontend README](apps/frontend/README.md).

### 3. Build the ESP32 firmware

```bash
make firmware-build
```

The initial target is an ESP32 DevKit using Arduino C++. The pin map and hardware constraints are documented in [the firmware README](apps/firmware/esp32/README.md).

## Development workflow

| Area | Command | Purpose |
| --- | --- | --- |
| Backend tests | `make api-test` | Run the FastAPI test suite |
| Backend lint | `make api-lint` | Check Python style and import hygiene |
| Frontend lint | `cd apps/frontend && npm run lint` | Run the React and TypeScript lint rules |
| Frontend build | `cd apps/frontend && npm run build` | Type-check and build the dashboard |
| Firmware build | `make firmware-build` | Compile the ESP32 PlatformIO project |
| Containerized API | `docker compose up --build backend` | Run the backend in Docker |

The GitHub Actions workflow runs backend linting and tests on pushes and pull requests.

## API contract

The ESP32 and backend communicate over a small HTTP JSON contract:

```http
POST /api/telemetry
X-API-Key: <device secret>
```

The request includes `device_id`, MQ-2 reading, temperature, humidity, warm-up status, and local-alarm status. The response returns the `buzzer` command and current device `state`.

The canonical schemas are in [packages/contracts/telemetry](packages/contracts/telemetry). Change the schemas deliberately and update every runtime that consumes them.

## Configuration and security

Copy `apps/backend/.env.example` to `apps/backend/.env` before running the API. Never commit `.env` files, camera URLs containing credentials, Telegram tokens, model weights, evidence frames, or runtime databases.

`API_KEY` protects the device heartbeat endpoint. Dashboard variables must use the `VITE_` prefix, but that prefix means the value is bundled into browser code—never place secrets there.

## Project status

| Component | Current foundation |
| --- | --- |
| Backend | FastAPI app, protected telemetry contract, health check, test and lint setup |
| Dashboard | React/Vite application scaffold ready; FireSight UI implementation pending |
| Firmware | ESP32 PlatformIO skeleton and initial pin map ready |
| Decision engine, storage, camera, detector | Planned layers based on the project design; implementation to follow |

## Contributing

Keep route handlers thin, place decision logic in framework-independent services, and add tests alongside behavior changes. Preserve the shared telemetry contract unless all affected clients are updated together.

Before opening a pull request, run:

```bash
make api-lint
make api-test
cd apps/frontend && npm run lint && npm run build
```

## Documentation

- [Repository architecture](docs/repository-layout.md)
- [Backend guide](apps/backend/README.md)
- [Frontend guide](apps/frontend/README.md)
- [ESP32 firmware guide](apps/firmware/esp32/README.md)

## License

No license has been selected yet. Add an explicit license before publishing or accepting external contributions.
