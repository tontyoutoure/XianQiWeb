# Backend test layout

This folder contains the M1 pytest skeleton based on `memory-bank/tests/m1-tests.md`.

- `unit/`: service and data-layer contracts (M1-UT-01..06)
- `api/auth/`: auth endpoint contracts (M1-API-01..12)
- `integration/ws/`: WebSocket auth contracts (M1-WS-01..03)

Current status: tests are intentionally skipped via `app_not_ready` until the FastAPI app and dependencies are implemented.
