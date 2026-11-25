#!/usr/bin/env bash
# Start the local backend (Linux/macOS helper for development validation)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/backend"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -r requirements.txt
if [[ ! -f .env && -f ../.env.example ]]; then
  cp ../.env.example .env
fi
alembic upgrade head
exec python -m uvicorn app.main:app --host 127.0.0.1 --port 8765
