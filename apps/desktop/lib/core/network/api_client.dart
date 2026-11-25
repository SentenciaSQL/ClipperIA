import 'dart:io';

import 'package:dio/dio.dart';

import '../config/app_config.dart';
import '../models/media_asset.dart';

/// HTTP client for localhost FastAPI communication.
class ApiClient {
  ApiClient({Dio? dio})
      : _dio = dio ??
            Dio(
              BaseOptions(
                baseUrl: AppConfig.baseUrl,
                connectTimeout: const Duration(seconds: 5),
                receiveTimeout: const Duration(seconds: 120),
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

  Future<List<ProjectItem>> listProjects({String? query}) async {
    final response = await _dio.get<List<dynamic>>(
      '/projects',
      queryParameters: {
        if (query != null && query.isNotEmpty) 'q': query,
      },
    );
    return (response.data ?? [])
        .map((e) => ProjectItem.fromJson(Map<String, dynamic>.from(e as Map)))
        .toList();
  }

  Future<ProjectItem> createProject({
    required String name,
    String? description,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/projects',
      data: {'name': name, 'description': description},
    );
    return ProjectItem.fromJson(response.data ?? {});
  }

  Future<void> deleteProject(String projectId) async {
    await _dio.delete('/projects/$projectId');
  }

  Future<List<MediaAsset>> listMedia({
    String? projectId,
    String? query,
  }) async {
    final response = await _dio.get<List<dynamic>>(
      '/media',
      queryParameters: {
        if (projectId != null) 'project_id': projectId,
        if (query != null && query.isNotEmpty) 'q': query,
      },
    );
    return (response.data ?? [])
        .map((e) => MediaAsset.fromJson(Map<String, dynamic>.from(e as Map)))
        .toList();
  }

  Future<MediaAsset> getMedia(String assetId) async {
    final response = await _dio.get<Map<String, dynamic>>('/media/$assetId');
    return MediaAsset.fromJson(response.data ?? {});
  }

  Future<MediaAsset> importMediaPath({
    required String path,
    String? projectId,
    bool manageOriginal = true,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/media/import-path',
      data: {
        'path': path,
        'project_id': projectId,
        'manage_original': manageOriginal,
      },
    );
    return MediaAsset.fromJson(response.data ?? {});
  }

  Future<MediaAsset> uploadMediaFile({
    required File file,
    String? projectId,
  }) async {
    final form = FormData.fromMap({
      'file': await MultipartFile.fromFile(
        file.path,
        filename: file.uri.pathSegments.last,
      ),
      if (projectId != null) 'project_id': projectId,
    });
    final response = await _dio.post<Map<String, dynamic>>(
      '/media/upload',
      data: form,
      options: Options(contentType: 'multipart/form-data'),
    );
    return MediaAsset.fromJson(response.data ?? {});
  }

  Future<MediaAsset> reprocessMedia(String assetId) async {
    final response =
        await _dio.post<Map<String, dynamic>>('/media/$assetId/reprocess');
    return MediaAsset.fromJson(response.data ?? {});
  }

  Future<void> deleteMedia(String assetId, {bool deleteFiles = true}) async {
    await _dio.delete(
      '/media/$assetId',
      queryParameters: {'delete_files': deleteFiles},
    );
  }

  Future<Map<String, dynamic>> enqueueTranscription(
    String mediaId, {
    String? modelSize,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/media/$mediaId/transcribe',
      queryParameters: {
        if (modelSize != null) 'model_size': modelSize,
      },
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> enqueueSemanticAnalysis(String mediaId) async {
    final response =
        await _dio.post<Map<String, dynamic>>('/media/$mediaId/analyze');
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> enqueueHighlightDetection(String mediaId) async {
    final response = await _dio
        .post<Map<String, dynamic>>('/media/$mediaId/highlights/detect');
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>?> getTranscript(String mediaId) async {
    try {
      final response =
          await _dio.get<Map<String, dynamic>>('/media/$mediaId/transcript');
      return response.data;
    } on DioException catch (error) {
      if (error.response?.statusCode == 404) return null;
      rethrow;
    }
  }

  Future<List<Map<String, dynamic>>> listHighlights({String? mediaId}) async {
    final response = await _dio.get<List<dynamic>>(
      '/highlights',
      queryParameters: {
        if (mediaId != null) 'media_asset_id': mediaId,
      },
    );
    return (response.data ?? [])
        .map((e) => Map<String, dynamic>.from(e as Map))
        .toList();
  }

  Future<Map<String, dynamic>> updateHighlightStatus(
    String highlightId,
    String status,
  ) async {
    final response = await _dio.patch<Map<String, dynamic>>(
      '/highlights/$highlightId',
      data: {'status': status},
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<List<Map<String, dynamic>>> listJobs({int limit = 50}) async {
    final response = await _dio.get<List<dynamic>>(
      '/jobs',
      queryParameters: {'limit': limit},
    );
    return (response.data ?? [])
        .map((e) => Map<String, dynamic>.from(e as Map))
        .toList();
  }

  Future<Map<String, dynamic>> getAiProviders() async {
    final response = await _dio.get<Map<String, dynamic>>('/ai/providers');
    return response.data ?? <String, dynamic>{};
  }

  String absoluteUrl(String relativeOrAbsolute) {
    if (relativeOrAbsolute.startsWith('http')) return relativeOrAbsolute;
    return 'http://${AppConfig.host}:${AppConfig.port}$relativeOrAbsolute';
  }
}
