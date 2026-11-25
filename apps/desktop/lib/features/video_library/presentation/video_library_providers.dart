import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/models/media_asset.dart';
import '../../../core/services/backend_connection.dart';

final mediaSearchProvider = StateProvider<String>((ref) => '');
final selectedProjectFilterProvider = StateProvider<String?>((ref) => null);

final projectsProvider = FutureProvider<List<ProjectItem>>((ref) async {
  final status = ref.watch(backendConnectionProvider);
  if (status.state != BackendConnectionState.connected) {
    return [];
  }
  return ref.watch(apiClientProvider).listProjects();
});

final mediaListProvider = FutureProvider<List<MediaAsset>>((ref) async {
  final status = ref.watch(backendConnectionProvider);
  if (status.state != BackendConnectionState.connected) {
    return [];
  }
  final query = ref.watch(mediaSearchProvider);
  final projectId = ref.watch(selectedProjectFilterProvider);
  return ref.watch(apiClientProvider).listMedia(
        query: query,
        projectId: projectId,
      );
});
