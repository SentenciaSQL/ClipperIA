import 'package:dio/dio.dart';

import '../config/app_config.dart';

/// HTTP client for localhost FastAPI communication.
class ApiClient {
  ApiClient({Dio? dio})
      : _dio = dio ??
            Dio(
              BaseOptions(
                baseUrl: AppConfig.baseUrl,
                connectTimeout: const Duration(seconds: 5),
                receiveTimeout: const Duration(seconds: 30),
                headers: const {'Content-Type': 'application/json'},
              ),
            );

  final Dio _dio;
  String? _token;

  Dio get dio => _dio;
  String? get token => _token;
  bool get isAuthenticated => _token != null && _token!.isNotEmpty;

  void setToken(String token) {
    _token = token;
    _dio.options.headers['X-API-Token'] = token;
  }

  Future<Map<String, dynamic>> bootstrap() async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/auth/bootstrap',
      options: Options(headers: {'X-API-Token': null}),
    );
    final data = response.data ?? <String, dynamic>{};
    final token = data['api_token'] as String?;
    if (token == null || token.isEmpty) {
      throw StateError('Bootstrap did not return an API token');
    }
    setToken(token);
    return data;
  }

  Future<Map<String, dynamic>> getHealth() async {
    final response = await _dio.get<Map<String, dynamic>>('/health');
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> getDashboardOverview() async {
    final response = await _dio.get<Map<String, dynamic>>('/dashboard/overview');
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> getSystemInfo() async {
    final response = await _dio.get<Map<String, dynamic>>('/system/info');
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> getRuntimeSettings() async {
    final response = await _dio.get<Map<String, dynamic>>('/settings/runtime');
    return response.data ?? <String, dynamic>{};
  }
}
