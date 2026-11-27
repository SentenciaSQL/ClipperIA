# Start the AI Clipping Platform local backend (Windows PowerShell)
# Usage (from repo root):
#   .\scripts\run_backend.ps1
#   .\scripts\run_backend.ps1 -SkipInstall   # skip pip when venv already exists
#   .\scripts\run_backend.ps1 -Port 8765
param(
    [switch]$SkipInstall,
    [int]$Port = 8765,
    [string]$HostAddress = "127.0.0.1"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"

Set-Location $Backend

function Find-Python {
    foreach ($candidate in @(
        { py -3.12 -c "import sys; print(sys.executable)" },
        { py -3.13 -c "import sys; print(sys.executable)" },
        { py -3 -c "import sys; print(sys.executable)" },
        { python -c "import sys; print(sys.executable)" }
    )) {
        try {
            $path = & $candidate 2>$null
            if ($LASTEXITCODE -eq 0 -and $path) {
                return ($path | Select-Object -Last 1).ToString().Trim()
            }
        } catch {
            # try next
        }
    }
    return $null
}

$VenvPython = Join-Path $Backend ".venv\Scripts\python.exe"
$VenvPip = Join-Path $Backend ".venv\Scripts\pip.exe"
$VenvAlembic = Join-Path $Backend ".venv\Scripts\alembic.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "==> Creating Python virtual environment (.venv)..."
    $py = Find-Python
    if (-not $py) {
        throw "Python 3.12+ not found. Install Python 3.12 and ensure 'py' or 'python' is on PATH."
    }
    Write-Host "    Using: $py"
    & $py -m venv .venv
    if (-not (Test-Path $VenvPython)) {
        throw "Failed to create .venv"
    }
    $SkipInstall = $false
}

if (-not $SkipInstall) {
    Write-Host "==> Ensuring backend dependencies..."
    & $VenvPython -m pip install --upgrade pip --quiet
    & $VenvPip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        throw "pip install failed"
    }
} else {
    Write-Host "==> Skipping dependency install (-SkipInstall)"
}

$EnvFile = Join-Path $Backend ".env"
$EnvExample = Join-Path $Root ".env.example"
if (-not (Test-Path $EnvFile) -and (Test-Path $EnvExample)) {
    Write-Host "==> Creating backend\.env from .env.example"
    Copy-Item $EnvExample $EnvFile
}

Write-Host "==> Applying database migrations..."
& $VenvAlembic upgrade head
if ($LASTEXITCODE -ne 0) {
    throw "alembic upgrade head failed"
}

Write-Host "==> Starting FastAPI on http://${HostAddress}:${Port}"
Write-Host "    API docs: http://${HostAddress}:${Port}/docs"
Write-Host "    Press Ctrl+C to stop."
& $VenvPython -m uvicorn app.main:app --host $HostAddress --port $Port
