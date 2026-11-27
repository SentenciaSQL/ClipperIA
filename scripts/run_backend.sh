#!/usr/bin/env bash
# Start the local FastAPI backend (Linux/macOS).
# Usage: ./scripts/run_backend.sh [--skip-install]
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/backend"
SKIP_INSTALL=0
if [[ "${1:-}" == "--skip-install" ]]; then
  SKIP_INSTALL=1
fi
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
  SKIP_INSTALL=0
fi
# shellcheck disable=SC1091
source .venv/bin/activate
if [[ "$SKIP_INSTALL" -eq 0 ]]; then
  python -m pip install --upgrade pip
  pip install -r requirements.txt
fi
if [[ ! -f .env && -f ../.env.example ]]; then
  cp ../.env.example .env
fi
alembic upgrade head
echo "Starting FastAPI on http://127.0.0.1:8765"
exec python -m uvicorn app.main:app --host 127.0.0.1 --port 8765
