# AI Clipping Platform

Local-first Windows desktop application for AI-powered video clipping.

Phase 1 delivers the foundation: Flutter desktop shell, FastAPI local backend, SQLite schema, REST + WebSocket communication, and hardware/dependency detection.

> Do not start Phase 2 until Phase 1 is manually validated and explicitly approved.

## Repository layout

```text
apps/desktop/          Flutter Windows/Linux desktop client
backend/               FastAPI + SQLAlchemy + Alembic
shared/contracts/      API contracts
models/                Reserved for local model assets
scripts/               Launch helpers (PowerShell + bash)
docs/                  Architecture and phase notes
```

## Prerequisites (Windows 10/11 x64)

| Component | Notes |
|-----------|--------|
| Flutter stable 3.24+ | Enable Windows desktop: `flutter config --enable-windows-desktop` |
| Visual Studio 2022 | Desktop development with C++ workload |
| Python 3.12 | Verify before installing CUDA-bound AI packages in later phases |
| FFmpeg | Must be on `PATH` (`ffmpeg -version`) |
| NVIDIA drivers / CUDA | Optional for Phase 1 detection; required later for NVENC/NVDEC + GPU inference |
| Git | Required |

### Exact Windows installation commands (PowerShell)

```powershell
# 1) Verify tooling
flutter --version
dart --version
py -3.12 --version
ffmpeg -version
nvidia-smi

# 2) Enable Flutter Windows desktop
flutter config --enable-windows-desktop
flutter doctor

# 3) Clone and enter the repository
cd <path-to-repo>

# 4) Backend virtual environment + dependencies
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item ..\.env.example .env
alembic upgrade head

# 5) Desktop dependencies
cd ..\apps\desktop
flutter pub get
```

## Run the application (Windows PowerShell)

Open **two** terminals from the repository root.

**Terminal A — backend**

```powershell
.\scripts\run_backend.ps1
```

Or manually:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --host 127.0.0.1 --port 8765
```

**Terminal B — desktop client**

```powershell
.\scripts\run_desktop.ps1
```

Or manually:

```powershell
cd apps\desktop
flutter run -d windows
```

Backend listens only on `http://127.0.0.1:8765`.

API docs (development): `http://127.0.0.1:8765/docs`

## Environment

See [`.env.example`](.env.example). Variables use the `ACP_` prefix.

Default data directory:

```text
Documents\AIClippingPlatform\
  database\
  media\originals|recordings|cache\
  projects\
  clips\
  exports\
  subtitles\
  thumbnails\
  models\
  logs\
```

## Phase 1 API surface

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/v1/health` | No | Liveness |
| GET | `/api/v1/auth/bootstrap` | No (localhost) | Session API token |
| GET | `/api/v1/system/info` | `X-API-Token` | Host / FFmpeg / GPU |
| GET | `/api/v1/dashboard/overview` | `X-API-Token` | Dashboard stats |
| GET | `/api/v1/settings/runtime` | `X-API-Token` | Runtime config |
| PUT | `/api/v1/settings` | `X-API-Token` | Persist setting |
| WS | `/api/v1/ws?token=...` | Query token | Real-time events |

Contract file: [`shared/contracts/openapi-phase1.yaml`](shared/contracts/openapi-phase1.yaml)

## Manual validation (Phase 1)

1. Start the backend; confirm `GET /api/v1/health` returns `"status":"ok"`.
2. Call `GET /api/v1/auth/bootstrap` and copy `api_token`.
3. Call `GET /api/v1/system/info` with header `X-API-Token: <token>` and verify FFmpeg detection.
4. Confirm GPU fields populate when `nvidia-smi` is available; otherwise an explicit unavailable message is returned.
5. Open the Flutter app; top bar should show **Backend online** and **WS**.
6. Dashboard counters load (zeros on a fresh database).
7. Settings page shows runtime paths and detection results.
8. Navigate all seven sidebar destinations to confirm the application shell.

PowerShell smoke checks:

```powershell
$health = Invoke-RestMethod http://127.0.0.1:8765/api/v1/health
$boot = Invoke-RestMethod http://127.0.0.1:8765/api/v1/auth/bootstrap
$headers = @{ "X-API-Token" = $boot.api_token }
Invoke-RestMethod http://127.0.0.1:8765/api/v1/system/info -Headers $headers
Invoke-RestMethod http://127.0.0.1:8765/api/v1/dashboard/overview -Headers $headers
```

## Known limitations (Phase 1)

- Media import, transcription, highlights, clip generation, live platforms, and packaging are not implemented yet.
- API token is generated per backend process unless `ACP_API_TOKEN` is set.
- This development environment may validate Linux desktop builds; production target remains Windows 10/11.
- GPU/CUDA detection requires NVIDIA drivers (`nvidia-smi`) on the host.

## Documentation

- [`docs/phase-1-foundation.md`](docs/phase-1-foundation.md)
