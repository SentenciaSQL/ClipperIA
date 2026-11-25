# Architecture notes (Phase 1)

## Modular monolith

The backend is a single FastAPI process with clear internal boundaries:

- `api/` — HTTP/WebSocket adapters only
- `services/` — application use cases
- `repositories/` — persistence access
- `infrastructure/` — SQLAlchemy, OS integrations
- `workers/`, `media/`, `ai/`, `integrations/` — reserved for later phases

## Local-first security

- Uvicorn binds to `127.0.0.1` by default.
- Desktop clients obtain a per-session token from `/auth/bootstrap`.
- Protected routes require `X-API-Token`.
- WebSocket clients must pass the same token as a query parameter.

## Storage

File paths and metadata live in SQLite. Binary media is never stored in the database. Default root is `Documents/AIClippingPlatform/` (or `~/AIClippingPlatform` when Documents is unavailable).

## Detection

`SystemDetectionService` probes:

- FFmpeg on `PATH` (version, NVENC/NVDEC encoder/decoder listings)
- NVIDIA GPU via `nvidia-smi` when present
- Host CPU/RAM via `psutil`

Missing GPU drivers are reported explicitly; the app still starts.
