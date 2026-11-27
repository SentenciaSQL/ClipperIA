# Create a Windows installer via Inno Setup (ISCC).
# Install Inno Setup 6: https://jrsoftware.org/isinfo.php
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Stage = Join-Path $Root "dist\windows\AIClippingPlatform"
$Iss = Join-Path $Root "packaging\windows\ai_clipping_platform.iss"
$Out = Join-Path $Root "dist\windows\installer"

if (-not (Test-Path $Stage)) {
    throw "Staged app missing. Run scripts\build_windows.ps1 first."
}
if (-not (Test-Path $Iss)) {
    throw "Inno Setup script missing: $Iss"
}

New-Item -ItemType Directory -Force -Path $Out | Out-Null

$iscc = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $iscc) {
    throw "ISCC.exe not found. Install Inno Setup 6 and retry."
}

& $iscc $Iss
Write-Host "==> Installer output under $Out"
