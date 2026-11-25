# Start the AI Clipping Platform local backend (Windows PowerShell)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"

Set-Location $Backend

if (-not (Test-Path ".venv")) {
    Write-Host "Creating Python virtual environment..."
    py -3.12 -m venv .venv
}

& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\pip.exe install -r requirements.txt

if (-not (Test-Path ".env") -and (Test-Path (Join-Path $Root ".env.example"))) {
    Copy-Item (Join-Path $Root ".env.example") ".env"
}

Write-Host "Applying database migrations..."
& .\.venv\Scripts\alembic.exe upgrade head

Write-Host "Starting FastAPI on http://127.0.0.1:8765 ..."
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8765
