@echo off
REM Double-click to launch the Flutter Windows desktop client.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\run_desktop.ps1" %*
if errorlevel 1 pause
