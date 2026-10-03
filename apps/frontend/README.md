# FireSight Dashboard

The FireSight dashboard is a React and Vite single-page application for monitoring device state, reviewing telemetry and evidence, and sending authorised controls to the local backend.

## Responsibilities

- Show the current device state, buzzer status, and heartbeat age.
- Display MQ-2, temperature, and humidity history.
- Present the latest verification frame and detector confidence when available.
- List warnings, alarms, silence actions, and resets.
- Provide clearly labelled controls for test buzzer, silence, and reset.

The dashboard is a monitoring and control interface. It must never be the only path to an alarm: the ESP32 and backend retain their independent safety logic.

## Prerequisites

- Node.js 20.19+ or 22.12+
- npm, which is included with Node.js
- The FireSight backend running locally for API integration

## Run locally

```bash
npm install
npm run dev
```

Vite serves the development application at `http://localhost:5173` by default.

| Command | Purpose |
| --- | --- |
| `npm run dev` | Start the Vite development server with hot-module replacement |
| `npm run build` | Type-check and generate a production build in `dist/` |
| `npm run lint` | Run the configured ESLint checks |
| `npm run preview` | Serve a locally built production bundle |

## Connect to the backend

Create `.env.local` in this directory:

```dotenv
VITE_API_BASE_URL=http://localhost:8000
```

Read the value in browser code with:

```ts
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL;
```

`VITE_` values are published into the client bundle. They are appropriate for public configuration such as the local API URL, but never for API keys, Telegram tokens, passwords, or other secrets.

The FastAPI backend permits `http://localhost:5173` by default through CORS. If your Vite server uses another origin, add that exact origin to `CORS_ORIGINS` in `apps/backend/.env`.

## API integration

Use the versioned schemas in [`packages/contracts/telemetry`](../../packages/contracts/telemetry) as the source of truth for device heartbeat fields and response states. The dashboard should not duplicate or redefine those types independently.

Planned API surfaces include:

| Purpose | API surface |
| --- | --- |
| Device status | `GET /api/status` and live WebSocket updates |
| Telemetry charts | `GET /api/telemetry/recent` |
| Events | `GET /api/events` |
| Latest camera frame | `GET /api/frame/latest` |
| Controls | `POST /api/test-buzzer`, `/api/silence`, `/api/reset` |

Only the protected heartbeat and health endpoints are in the initial backend scaffold. Add frontend features only when the corresponding backend endpoint and tests exist.

## Suggested application structure

Group future dashboard code by feature rather than by file type:

```text
src/
  app/              application shell, router, providers
  features/
    device-status/  live state and alarm presentation
    telemetry/      charts and range controls
    incidents/      evidence and event history
    controls/       test, silence, and reset actions
  shared/
    api/            typed HTTP and WebSocket client
    ui/             reusable visual components
    lib/            formatting and utility functions
```

## Development standards

- Treat backend state as the source of truth; do not infer alarm status only from visual styling.
- Show an explicit offline state when heartbeats stop.
- Make silence and reset actions deliberate and clearly distinguish them from an alarm acknowledgement.
- Keep secrets out of browser code and out of all committed `.env` files.
- Run `npm run lint` and `npm run build` before opening a pull request.
