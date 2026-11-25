# Phase 1 — Foundation & Architecture

## Scope

Phase 1 delivers the monorepo foundation, local FastAPI backend, Flutter desktop shell, REST + WebSocket communication, SQLite/SQLAlchemy/Alembic schema, centralized configuration, structured logging, and FFmpeg/GPU detection.

Later feature modules are navigable in the shell but intentionally not implemented yet.

## Architecture

- **Frontend**: Flutter Desktop (`apps/desktop`) with Riverpod, GoRouter, Dio, WebSocket.
- **Backend**: FastAPI modular monolith (`backend/app`) bound to `127.0.0.1` only.
- **Contracts**: `shared/contracts/openapi-phase1.yaml`
- **Persistence**: SQLite under `Documents/AIClippingPlatform/database/`
- **Auth**: Per-process local API token from `/api/v1/auth/bootstrap`, sent as `X-API-Token`.

Business logic lives in services/repositories. Route handlers only validate input and delegate.

## Database entities (initial schema)

Project, MediaAsset, SourceConnection, LiveSession, ProcessingJob, Transcript, Highlight, Clip, ClipVersion, Subtitle, Export, AppSetting.

## Manual validation checklist

1. Backend health returns `status: ok`.
2. Bootstrap returns `api_token`.
3. Authenticated `/system/info` reports FFmpeg/GPU detection.
4. Dashboard overview returns zeroed counters on a fresh install.
5. WebSocket accepts `?token=` and answers `ping` with `pong`.
6. Flutter shell connects and shows backend online status.
