# FireSight Backend

The backend owns device authentication, decision-engine orchestration, camera/detector adapters, storage, and the live REST/WebSocket API.

Install it from the repository root with `make api-install`, copy `.env.example` to `.env`, and run `make api-run`. The currently runnable baseline provides a protected heartbeat endpoint and health endpoint; expand it through the layers under `src/firesight_backend/` rather than placing business rules in route handlers.
