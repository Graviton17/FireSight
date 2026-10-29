# FireSight Frontend

One page: a map of Gujarat with two kinds of markers, loaded from the backend
for whatever area is on screen (refetched on every pan/zoom and every 10 s).

- **Fire stations** (black square; the number is how many times it was called).
  Click one for its phone, address and the list of **calls from devices**: which
  device called, when, how far away, and whether the camera confirmed the fire.
- **Devices** (round): outlined = online, red pulsing = fire detected, grey =
  offline (no reading for 60 s). Click one for the **Live** reading and location,
  the **Log** of recent readings, and **Triggers**: every alarm, the station it
  called, and camera snapshots.

Clicking a call or trigger jumps to the device or station at the other end, and
a dashed line joins them on the map.

React 19 + Vite, [shadcn/ui](https://ui.shadcn.com) (neutral palette, follows
the OS light/dark setting), Leaflet with OpenStreetMap tiles.

## Run

Start the backend first (`backend/`, port 8000) and apply its migrations,
including `20261030120000_fire_alerts_and_map.sql`. Then:

```bash
npm install
npm run dev
```

Open http://localhost:5173. Vite proxies `/api` to `http://localhost:8000`;
set `FIRESIGHT_API_URL` to proxy elsewhere, or `VITE_API_BASE_URL` to call a
backend on another origin directly (add that origin to `server.cors_origins`).

## Deploying (e.g. Vercel + backend over ngrok)

1. Set `VITE_API_BASE_URL` in Vercel to the backend's public URL (e.g. the
   ngrok URL) and redeploy. It is baked in at build time.
2. Add the frontend's origin (e.g. `https://your-app.vercel.app`) to
   `server.cors_origins` in `backend/config.json` and restart the backend.
3. Free ngrok shows browsers a warning page instead of the API; the client
   sends `ngrok-skip-browser-warning` whenever `VITE_API_BASE_URL` is set, so
   this works without extra setup.

## Layout

```
src/
  api.ts                    typed client for backend/app/api/v1
  App.tsx                   the map, markers, selection
  components/MapOverlay.tsx title, legend, active fires
  components/map/icons.ts   marker icons
  components/panel/         StationPanel, DevicePanel
  components/ui/            shadcn/ui (add more with `npx shadcn@latest add <name>`)
  hooks/                    viewport loading, polling
```
