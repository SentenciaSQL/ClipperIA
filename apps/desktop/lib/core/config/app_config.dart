/// Central frontend configuration for the local backend.
class AppConfig {
  const AppConfig._();

  static const String appName = 'AI Clipping Platform';
  static const String host = '127.0.0.1';
  static const int port = 8765;
  static const String apiPrefix = '/api/v1';

  static String get baseUrl => 'http://$host:$port$apiPrefix';
  static String get bootstrapUrl => '$baseUrl/auth/bootstrap';
  static String get healthUrl => '$baseUrl/health';

  static String websocketUrl(String token) =>
      'ws://$host:$port$apiPrefix/ws?token=${Uri.encodeQueryComponent(token)}';
}
