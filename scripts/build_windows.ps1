# Build Flutter Windows desktop release + stage backend for packaging.
# Prerequisites: Flutter Windows desktop enabled, VS 2022 C++ workload, Python 3.12.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Desktop = Join-Path $Root "apps\desktop"
$Backend = Join-Path $Root "backend"
$Dist = Join-Path $Root "dist\windows"
$Stage = Join-Path $Dist "AIClippingPlatform"

Write-Host "==> Building Flutter Windows release"
Push-Location $Desktop
flutter pub get
flutter build windows --release
Pop-Location

$FlutterOut = Join-Path $Desktop "build\windows\x64\runner\Release"
if (-not (Test-Path $FlutterOut)) {
    throw "Flutter release output not found at $FlutterOut"
}

Write-Host "==> Staging application at $Stage"
if (Test-Path $Stage) { Remove-Item -Recurse -Force $Stage }
New-Item -ItemType Directory -Path $Stage | Out-Null
Copy-Item -Recurse -Force "$FlutterOut\*" $Stage

$BackendStage = Join-Path $Stage "backend"
New-Item -ItemType Directory -Path $BackendStage | Out-Null
Copy-Item -Recurse -Force (Join-Path $Backend "app") (Join-Path $BackendStage "app")
Copy-Item -Force (Join-Path $Backend "requirements.txt") $BackendStage
Copy-Item -Force (Join-Path $Backend "alembic.ini") $BackendStage
Copy-Item -Recurse -Force (Join-Path $Backend "alembic") (Join-Path $BackendStage "alembic")
Copy-Item -Force (Join-Path $Root ".env.example") (Join-Path $Stage ".env.example")

$Launcher = @"
@echo off
setlocal
cd /d "%~dp0"
if not exist backend\.venv (
  echo Creating backend virtualenv...
  py -3.12 -m venv backend\.venv
  call backend\.venv\Scripts\activate.bat
  python -m pip install --upgrade pip
  pip install -r backend\requirements.txt
) else (
  call backend\.venv\Scripts\activate.bat
)
start "AI Clipping Backend" cmd /c "cd /d ""%~dp0backend"" && .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8765"
timeout /t 2 >nul
start "" "%~dp0ai_clipping_platform.exe"
"@
Set-Content -Path (Join-Path $Stage "Start-AIClippingPlatform.bat") -Value $Launcher -Encoding ASCII

Write-Host "==> Stage ready: $Stage"
Write-Host "Next: run scripts\package_windows_installer.ps1 (requires Inno Setup)."
