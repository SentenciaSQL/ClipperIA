@echo off
REM Double-click or run from any folder: starts the local FastAPI backend.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\run_backend.ps1" %*
if errorlevel 1 pause
