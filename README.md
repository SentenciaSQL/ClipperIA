# AI Clipping Platform

Local-first Windows desktop application for AI-powered video clipping.

Phases **1–9** are implemented:

1. Foundation
2. Media library
3. Transcription / semantic analysis
4. Highlight detection
5. Automatic clip generation & export presets
6. Clip editor (captions, reframe, Demucs optional)
7. Live YouTube/Twitch/Kick + authorized OBS/local capture
8. Hybrid AI, batch automation, descriptions/hashtags, profiles
9. Optimization, model/storage management, Windows packaging

## Repository layout

```text
apps/desktop/          Flutter Windows/Linux desktop client
backend/               FastAPI + SQLAlchemy + Alembic
shared/contracts/      API contracts
models/                Reserved for local model assets
packaging/windows/     Inno Setup installer script
scripts/               Launch + Windows build helpers
docs/                  Architecture and phase notes
```

## Prerequisites (Windows 10/11 x64)

| Component | Notes |
|-----------|--------|
| Flutter stable 3.24+ | Enable Windows desktop: `flutter config --enable-windows-desktop` |
| Visual Studio 2022 | Desktop development with C++ workload |
| Python 3.12 | Verify before installing CUDA-bound AI packages |
| FFmpeg | Must be on `PATH` (`ffmpeg -version`) |
| NVIDIA drivers / CUDA | Optional; required for NVENC/NVDEC + GPU inference |
| Inno Setup 6 | Optional; only for building the installer |
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
# CPU torch (dev) OR CUDA torch for NVIDIA hosts:
#   pip install torch --index-url https://download.pytorch.org/whl/cpu
#   pip install torch --index-url https://download.pytorch.org/whl/cu121
Copy-Item ..\.env.example .env
alembic upgrade head

# Optional local LLM for semantic analysis
# Install Ollama, then: ollama pull qwen3:8b

# 5) Desktop dependencies
cd ..\apps\desktop
flutter pub get
```

## Run the application (Windows)

From the repository root you can use **one command** (or double-click the `.cmd` files in Explorer).

| Goal | Command / file |
|------|----------------|
| Backend only | `.\start-backend.cmd` or `.\scripts\run_backend.ps1` |
| Desktop only | `.\start-desktop.cmd` or `.\scripts\run_desktop.ps1` |
| Both (backend in a new window) | `.\start-dev.cmd` |

`run_backend.ps1` creates `.venv` if needed, installs dependencies, copies `.env`, runs `alembic upgrade head`, and starts uvicorn.  
Faster restarts after the first setup:

```powershell
.\scripts\run_backend.ps1 -SkipInstall
```

Backend listens only on `http://127.0.0.1:8765`.

API docs (development): `http://127.0.0.1:8765/docs`

## Windows packaging

```powershell
.\scripts\build_windows.ps1
.\scripts\package_windows_installer.ps1   # requires Inno Setup 6
```

Staged app: `dist\windows\AIClippingPlatform\`  
Installer: `dist\windows\installer\`

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

## API surface (selected)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/health` | Liveness |
| GET | `/api/v1/auth/bootstrap` | Session API token |
| GET | `/api/v1/system/info` | Host / FFmpeg / GPU |
| GET | `/api/v1/system/resources` | RAM/GPU tips + concurrency |
| GET | `/api/v1/ai/providers` | Provider readiness |
| GET | `/api/v1/ai/providers/status` | Local/cloud registry status |
| POST | `/api/v1/ai/providers/mode` | Set `local` / `cloud` / `auto` |
| GET/POST | `/api/v1/profiles` | Processing profiles |
| POST | `/api/v1/batch/process` | Batch automation job |
| POST | `/api/v1/clips/{id}/metadata` | AI description + hashtags |
| POST | `/api/v1/clips/{id}/versions` | Alternative aspect ratios |
| GET/POST | `/api/v1/models` | Whisper model management |
| GET/POST | `/api/v1/storage/*` | Usage + cache cleanup |
| WS | `/api/v1/ws?token=...` | Real-time job events |

## Manual validation

1. Start backend + desktop; Settings shows AI providers, profiles, storage.
2. Import a short video → **Batch process** (Library).
3. Open Clip Editor → **AI description** and **Alt ratios**.
4. Settings → Ensure Whisper `tiny`, Cleanup cache.
5. Optional: set `ACP_CLOUD_LLM_API_KEY` and switch provider mode to `cloud` / `auto`.

## Documentation

- [`docs/architecture.md`](docs/architecture.md)
- [`docs/phase-1-foundation.md`](docs/phase-1-foundation.md)
- [`docs/phase-2-4.md`](docs/phase-2-4.md)
- [`docs/phase-5-7.md`](docs/phase-5-7.md)
- [`docs/phase-8-9.md`](docs/phase-8-9.md)
