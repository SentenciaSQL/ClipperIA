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

  Future<Map<String, dynamic>> getAiProviderStatus() async {
    final response =
        await _dio.get<Map<String, dynamic>>('/ai/providers/status');
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> setAiProviderMode(String mode) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/ai/providers/mode',
      data: {'mode': mode},
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> generateClipMetadata(
    String clipId, {
    String platform = 'tiktok',
    String? provider,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/clips/$clipId/metadata',
      data: {
        'platform': platform,
        if (provider != null) 'provider': provider,
      },
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> listProfiles() async {
    final response = await _dio.get<Map<String, dynamic>>('/profiles');
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> setActiveProfile(String profileId) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/profiles/active',
      data: {'profile_id': profileId},
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> enqueueBatchProcess({
    required List<String> mediaAssetIds,
    String? profileId,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/batch/process',
      data: {
        'media_asset_ids': mediaAssetIds,
        if (profileId != null) 'profile_id': profileId,
      },
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> generateAlternativeVersions(String clipId) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/clips/$clipId/versions',
      data: <String, dynamic>{},
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> getModelsInventory() async {
    final response = await _dio.get<Map<String, dynamic>>('/models');
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> ensureWhisperModel({String modelSize = 'base'}) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/models/whisper/ensure',
      data: {'model_size': modelSize},
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> getStorageUsage() async {
    final response = await _dio.get<Map<String, dynamic>>('/storage/usage');
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> cleanupStorage({
    double olderThanHours = 72,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/storage/cleanup',
      data: {'older_than_hours': olderThanHours},
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> getSystemResources() async {
    final response = await _dio.get<Map<String, dynamic>>('/system/resources');
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> getClipPresets() async {
    final response = await _dio.get<Map<String, dynamic>>('/clips/presets');
    return response.data ?? <String, dynamic>{};
  }

  Future<List<Map<String, dynamic>>> listClips({String? mediaId}) async {
    final response = await _dio.get<List<dynamic>>(
      '/clips',
      queryParameters: {
        if (mediaId != null) 'media_asset_id': mediaId,
      },
    );
    return (response.data ?? [])
        .map((e) => Map<String, dynamic>.from(e as Map))
        .toList();
  }

  Future<Map<String, dynamic>> getClip(String clipId) async {
    final response = await _dio.get<Map<String, dynamic>>('/clips/$clipId');
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> updateClip(
    String clipId,
    Map<String, dynamic> body,
  ) async {
    final response =
        await _dio.patch<Map<String, dynamic>>('/clips/$clipId', data: body);
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> generateClips({
    required String mediaId,
    String aspectRatio = '9:16',
    double maxDuration = 30,
    int limit = 5,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/clips/generate',
      data: {
        'media_asset_id': mediaId,
        'aspect_ratio': aspectRatio,
        'max_duration': maxDuration,
        'limit': limit,
      },
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> renderClip(
    String clipId, {
    String versionLabel = 'edited',
    Map<String, dynamic>? settings,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/clips/$clipId/render',
      data: {
        'version_label': versionLabel,
        'settings': settings ?? <String, dynamic>{},
      },
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> generateSubtitles(String clipId) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/clips/$clipId/subtitles',
      data: <String, dynamic>{},
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> reframeClip(String clipId) async {
    final response =
        await _dio.post<Map<String, dynamic>>('/clips/$clipId/reframe');
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> separateAudio(String clipId) async {
    final response =
        await _dio.post<Map<String, dynamic>>('/clips/$clipId/separate-audio');
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> getClipEditor(String clipId) async {
    final response =
        await _dio.get<Map<String, dynamic>>('/clips/$clipId/editor');
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> patchClipEditor(
    String clipId,
    Map<String, dynamic> body,
  ) async {
    final response = await _dio.patch<Map<String, dynamic>>(
      '/clips/$clipId/editor',
      data: body,
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<List<Map<String, dynamic>>> listAudioTracks(String clipId) async {
    final response = await _dio.get<List<dynamic>>('/clips/$clipId/audio-tracks');
    return (response.data ?? [])
        .map((e) => Map<String, dynamic>.from(e as Map))
        .toList();
  }

  Future<Map<String, dynamic>> updateAudioTrack(
    String trackId,
    Map<String, dynamic> body,
  ) async {
    final response = await _dio.patch<Map<String, dynamic>>(
      '/audio-tracks/$trackId',
      data: body,
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> importAudioTrack(
    String clipId, {
    required String path,
    String? name,
    String kind = 'music',
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/clips/$clipId/audio-tracks/import',
      data: {
        'path': path,
        if (name != null) 'name': name,
        'kind': kind,
      },
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<void> deleteAudioTrack(String trackId) async {
    await _dio.delete('/audio-tracks/$trackId');
  }

  Future<Map<String, dynamic>> duplicateAudioTrack(String trackId) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/audio-tracks/$trackId/duplicate',
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> getCaptionPresets() async {
    final response = await _dio.get<Map<String, dynamic>>('/captions/presets');
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> updateSubtitlesAdvanced(
    String subtitleId, {
    required List<Map<String, dynamic>> cues,
    Map<String, dynamic>? style,
    String? preset,
  }) async {
    final response = await _dio.patch<Map<String, dynamic>>(
      '/subtitles/$subtitleId/advanced',
      data: {
        'cues': cues,
        if (style != null) 'style': style,
        if (preset != null) 'preset': preset,
      },
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> addCaptionWordOverride(
    String subtitleId, {
    required int cueIndex,
    required Map<String, dynamic> override,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/subtitles/$subtitleId/overrides',
      data: {'cue_index': cueIndex, 'override': override},
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> generateSubtitlesAdvanced(
    String clipId, {
    String preset = 'classic',
    bool replaceExisting = false,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/clips/$clipId/subtitles/advanced',
      data: {
        'preset': preset,
        'replace_existing': replaceExisting,
      },
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> exportClip(
    String clipId, {
    String preset = 'tiktok',
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/clips/$clipId/export',
      data: {'preset': preset},
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<List<Map<String, dynamic>>> listExports({String? clipId}) async {
    final response = await _dio.get<List<dynamic>>(
      '/exports',
      queryParameters: {
        if (clipId != null) 'clip_id': clipId,
      },
    );
    return (response.data ?? [])
        .map((e) => Map<String, dynamic>.from(e as Map))
        .toList();
  }

  Future<Map<String, dynamic>> getLivePlatforms() async {
    final response = await _dio.get<Map<String, dynamic>>('/live/platforms');
    return response.data ?? <String, dynamic>{};
  }

  Future<List<Map<String, dynamic>>> listLiveConnections() async {
    final response = await _dio.get<List<dynamic>>('/live/connections');
    return (response.data ?? [])
        .map((e) => Map<String, dynamic>.from(e as Map))
        .toList();
  }

  Future<Map<String, dynamic>> createLiveConnection({
    required String platform,
    required String displayName,
    String? externalAccountId,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/live/connections',
      data: {
        'platform': platform,
        'display_name': displayName,
        if (externalAccountId != null) 'external_account_id': externalAccountId,
      },
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> startLiveOAuth({
    required String platform,
    required String redirectUri,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/live/oauth/start',
      data: {'platform': platform, 'redirect_uri': redirectUri},
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<List<Map<String, dynamic>>> listLiveSessions() async {
    final response = await _dio.get<List<dynamic>>('/live/sessions');
    return (response.data ?? [])
        .map((e) => Map<String, dynamic>.from(e as Map))
        .toList();
  }

  Future<Map<String, dynamic>> startLocalCapture({
    required String connectionId,
    required String inputUrl,
    String? title,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/live/sessions/capture',
      data: {
        'connection_id': connectionId,
        'input_url': inputUrl,
        if (title != null) 'title': title,
      },
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> stopLiveSession(String sessionId) async {
    final response = await _dio
        .post<Map<String, dynamic>>('/live/sessions/$sessionId/stop');
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> enqueueLiveHighlights(String sessionId) async {
    final response = await _dio
        .post<Map<String, dynamic>>('/live/sessions/$sessionId/highlights');
    return response.data ?? <String, dynamic>{};
  }

  String absoluteUrl(String relativeOrAbsolute) {
    if (relativeOrAbsolute.startsWith('http')) return relativeOrAbsolute;
    return 'http://${AppConfig.host}:${AppConfig.port}$relativeOrAbsolute';
  }
}
