# AI Clipping Platform — Desktop Client

Flutter desktop application (Windows primary target; Linux enabled for development validation).

## Stack

- Flutter / Dart
- Riverpod
- GoRouter
- Dio
- WebSocket (`web_socket_channel`)
- Google Fonts (IBM Plex Sans)

## Run (Windows)

Ensure the backend is running on `127.0.0.1:8765`, then:

```powershell
cd apps\desktop
flutter pub get
flutter run -d windows
```

## Phase 1 scope

- Application shell with seven navigation destinations
- Local backend bootstrap, REST calls, and WebSocket connection
- Dashboard and Settings wired to live backend data
- Later feature modules appear as scheduled-phase destinations
