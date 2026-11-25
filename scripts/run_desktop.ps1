# Launch the Flutter Windows desktop client
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Desktop = Join-Path $Root "apps\desktop"

Set-Location $Desktop
flutter pub get
flutter run -d windows
