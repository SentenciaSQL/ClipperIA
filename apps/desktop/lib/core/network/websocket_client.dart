import 'dart:async';
import 'dart:convert';

import 'package:web_socket_channel/web_socket_channel.dart';

import '../config/app_config.dart';

/// Real-time event client for backend job/status notifications.
class WebSocketClient {
  WebSocketChannel? _channel;
  StreamSubscription<dynamic>? _subscription;
  final _controller = StreamController<Map<String, dynamic>>.broadcast();
  Timer? _pingTimer;
  bool _connected = false;

  Stream<Map<String, dynamic>> get events => _controller.stream;
  bool get isConnected => _connected;

  Future<void> connect(String token) async {
    await disconnect();
    final uri = Uri.parse(AppConfig.websocketUrl(token));
    _channel = WebSocketChannel.connect(uri);
    _connected = true;
    _subscription = _channel!.stream.listen(
      (event) {
        try {
          final decoded = event is String
              ? jsonDecode(event) as Map<String, dynamic>
              : Map<String, dynamic>.from(event as Map);
          _controller.add(decoded);
        } catch (_) {
          _controller.add({'type': 'raw', 'payload': {'data': event.toString()}});
        }
      },
      onError: (Object error) {
        _connected = false;
        _controller.add({'type': 'error', 'payload': {'message': error.toString()}});
      },
      onDone: () {
        _connected = false;
        _controller.add({'type': 'disconnected', 'payload': {}});
      },
    );

    _pingTimer = Timer.periodic(const Duration(seconds: 20), (_) {
      send({'type': 'ping'});
    });

    send({
      'type': 'subscribe',
      'channels': ['jobs', 'system'],
    });
  }

  void send(Map<String, dynamic> message) {
    _channel?.sink.add(jsonEncode(message));
  }

  Future<void> disconnect() async {
    _pingTimer?.cancel();
    _pingTimer = null;
    await _subscription?.cancel();
    _subscription = null;
    await _channel?.sink.close();
    _channel = null;
    _connected = false;
  }

  Future<void> dispose() async {
    await disconnect();
    await _controller.close();
  }
}
