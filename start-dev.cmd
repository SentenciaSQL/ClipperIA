@echo off
REM One-shot local stack: backend in a new window + Flutter desktop here.
cd /d "%~dp0"

echo Starting backend in a new window...
start "ClipperIA Backend" powershell -NoProfile -ExecutionPolicy Bypass -NoExit -File "%~dp0scripts\run_backend.ps1" -SkipInstall

echo Waiting a few seconds for the API to come up...
timeout /t 4 /nobreak >nul

echo Starting Flutter desktop...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\run_desktop.ps1"
if errorlevel 1 pause
