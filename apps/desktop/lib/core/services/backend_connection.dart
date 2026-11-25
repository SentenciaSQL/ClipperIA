import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../network/api_client.dart';
import '../network/websocket_client.dart';

enum BackendConnectionState {
  disconnected,
  connecting,
  connected,
  error,
}

class BackendStatus {
  const BackendStatus({
    required this.state,
    this.message,
    this.appVersion,
    this.websocketConnected = false,
  });

  final BackendConnectionState state;
  final String? message;
  final String? appVersion;
  final bool websocketConnected;

  BackendStatus copyWith({
    BackendConnectionState? state,
    String? message,
    String? appVersion,
    bool? websocketConnected,
  }) {
    return BackendStatus(
      state: state ?? this.state,
      message: message ?? this.message,
      appVersion: appVersion ?? this.appVersion,
      websocketConnected: websocketConnected ?? this.websocketConnected,
    );
  }
}

class BackendConnectionNotifier extends StateNotifier<BackendStatus> {
  BackendConnectionNotifier(this._api, this._ws)
      : super(const BackendStatus(state: BackendConnectionState.disconnected));

  final ApiClient _api;
  final WebSocketClient _ws;

  Future<void> connect() async {
    state = state.copyWith(
      state: BackendConnectionState.connecting,
      message: 'Connecting to local backend…',
    );
    try {
      final bootstrap = await _api.bootstrap();
      final health = await _api.getHealth();
      await _ws.connect(_api.token!);
      state = BackendStatus(
        state: BackendConnectionState.connected,
        message: 'Connected to ${bootstrap['base_url']}',
        appVersion: health['version'] as String?,
        websocketConnected: _ws.isConnected,
      );
    } catch (error) {
      state = BackendStatus(
        state: BackendConnectionState.error,
        message: error.toString(),
        websocketConnected: false,
      );
    }
  }

  Future<void> disconnect() async {
    await _ws.disconnect();
    state = const BackendStatus(state: BackendConnectionState.disconnected);
  }
}

final apiClientProvider = Provider<ApiClient>((ref) {
  final client = ApiClient();
  ref.onDispose(() {});
  return client;
});

final webSocketClientProvider = Provider<WebSocketClient>((ref) {
  final client = WebSocketClient();
  ref.onDispose(client.dispose);
  return client;
});

final backendConnectionProvider =
    StateNotifierProvider<BackendConnectionNotifier, BackendStatus>((ref) {
  return BackendConnectionNotifier(
    ref.watch(apiClientProvider),
    ref.watch(webSocketClientProvider),
  );
});

final dashboardOverviewProvider = FutureProvider<Map<String, dynamic>>((ref) async {
  final status = ref.watch(backendConnectionProvider);
  if (status.state != BackendConnectionState.connected) {
    throw StateError('Backend not connected');
  }
  return ref.watch(apiClientProvider).getDashboardOverview();
});

final systemInfoProvider = FutureProvider<Map<String, dynamic>>((ref) async {
  final status = ref.watch(backendConnectionProvider);
  if (status.state != BackendConnectionState.connected) {
    throw StateError('Backend not connected');
  }
  return ref.watch(apiClientProvider).getSystemInfo();
});

final runtimeSettingsProvider = FutureProvider<Map<String, dynamic>>((ref) async {
  final status = ref.watch(backendConnectionProvider);
  if (status.state != BackendConnectionState.connected) {
    throw StateError('Backend not connected');
  }
  return ref.watch(apiClientProvider).getRuntimeSettings();
});

final websocketEventsProvider = StreamProvider<Map<String, dynamic>>((ref) {
  return ref.watch(webSocketClientProvider).events;
});
