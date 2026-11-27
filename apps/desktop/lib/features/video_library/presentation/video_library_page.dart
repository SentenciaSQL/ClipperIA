import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/config/app_config.dart';
import '../../../core/models/media_asset.dart';
import '../../../core/services/backend_connection.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets/section_header.dart';
import 'video_library_providers.dart';

class VideoLibraryPage extends ConsumerStatefulWidget {
  const VideoLibraryPage({super.key});

  @override
  ConsumerState<VideoLibraryPage> createState() => _VideoLibraryPageState();
}

class _VideoLibraryPageState extends ConsumerState<VideoLibraryPage> {
  final _searchController = TextEditingController();
  bool _busy = false;
  String? _statusMessage;

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _refresh() async {
    ref.invalidate(mediaListProvider);
    ref.invalidate(projectsProvider);
    ref.invalidate(dashboardOverviewProvider);
  }

  Future<void> _importVideos() async {
    final result = await FilePicker.pickFiles(
      type: FileType.custom,
      allowedExtensions: const ['mp4', 'mkv', 'mov'],
      allowMultiple: true,
    );
    if (result == null || result.files.isEmpty) return;

    setState(() {
      _busy = true;
      _statusMessage = 'Importing ${result.files.length} file(s)…';
    });

    final api = ref.read(apiClientProvider);
    final projectId = ref.read(selectedProjectFilterProvider);
    var imported = 0;
    try {
      for (final file in result.files) {
        final path = file.path;
        if (path == null) continue;
        await api.importMediaPath(path: path, projectId: projectId);
        imported += 1;
      }
      setState(() => _statusMessage = 'Imported $imported video(s).');
      await _refresh();
    } catch (error) {
      setState(() => _statusMessage = 'Import failed: $error');
    } finally {
      setState(() => _busy = false);
    }
  }

  Future<void> _createProject() async {
    final nameController = TextEditingController();
    final descController = TextEditingController();
    final created = await showDialog<bool>(
      context: context,
      builder: (context) {
        return AlertDialog(
          backgroundColor: AppTheme.surface,
          title: const Text('New project'),
          content: SizedBox(
            width: 420,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: nameController,
                  decoration: const InputDecoration(labelText: 'Name'),
                  autofocus: true,
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: descController,
                  decoration: const InputDecoration(labelText: 'Description'),
                  maxLines: 2,
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Create'),
            ),
          ],
        );
      },
    );

    if (created != true || nameController.text.trim().isEmpty) return;
    try {
      await ref.read(apiClientProvider).createProject(
            name: nameController.text.trim(),
            description: descController.text.trim().isEmpty
                ? null
                : descController.text.trim(),
          );
      await _refresh();
    } catch (error) {
      setState(() => _statusMessage = 'Project create failed: $error');
    }
  }

  Future<void> _batchProcessVisible() async {
    final items = ref.read(mediaListProvider).asData?.value ?? [];
    if (items.isEmpty) {
      setState(() => _statusMessage = 'No media to batch process.');
      return;
    }
    setState(() {
      _busy = true;
      _statusMessage = 'Queueing batch for ${items.length} video(s)…';
    });
    try {
      final job = await ref.read(apiClientProvider).enqueueBatchProcess(
            mediaAssetIds: items.map((e) => e.id).toList(),
          );
      setState(
        () => _statusMessage =
            'Batch job ${job['id']} queued (${job['status']}).',
      );
    } catch (error) {
      setState(() => _statusMessage = 'Batch queue failed: $error');
    } finally {
      setState(() => _busy = false);
    }
  }

  Future<void> _reprocess(MediaAsset asset) async {
    setState(() {
      _busy = true;
      _statusMessage = 'Reprocessing ${asset.originalFilename}…';
    });
    try {
      await ref.read(apiClientProvider).reprocessMedia(asset.id);
      setState(() => _statusMessage = 'Reprocessed ${asset.originalFilename}');
      await _refresh();
    } catch (error) {
      setState(() => _statusMessage = 'Reprocess failed: $error');
    } finally {
      setState(() => _busy = false);
    }
  }

  Future<void> _transcribe(MediaAsset asset) async {
    setState(() {
      _busy = true;
      _statusMessage = 'Queueing transcription for ${asset.originalFilename}…';
    });
    try {
      final job =
          await ref.read(apiClientProvider).enqueueTranscription(asset.id);
      setState(
        () => _statusMessage =
            'Transcription job ${job['id']} queued (${job['status']}).',
      );
    } catch (error) {
      setState(() => _statusMessage = 'Transcription queue failed: $error');
    } finally {
      setState(() => _busy = false);
    }
  }

  Future<void> _delete(MediaAsset asset) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: AppTheme.surface,
        title: const Text('Remove from library'),
        content: Text(
          'Remove "${asset.originalFilename}"?\nManaged copies and thumbnails will be deleted. Source files outside the library are not modified.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Remove'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    try {
      await ref.read(apiClientProvider).deleteMedia(asset.id);
      await _refresh();
    } catch (error) {
      setState(() => _statusMessage = 'Delete failed: $error');
    }
  }

  void _showDetails(MediaAsset asset) {
    showDialog<void>(
      context: context,
      builder: (context) {
        return AlertDialog(
          backgroundColor: AppTheme.surface,
          title: Text(asset.originalFilename),
          content: SizedBox(
            width: 480,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _detail('Duration', asset.durationLabel),
                _detail('Resolution', asset.resolutionLabel),
                _detail(
                  'Frame rate',
                  asset.frameRate == null
                      ? 'n/a'
                      : asset.frameRate!.toStringAsFixed(2),
                ),
                _detail('Video codec', asset.videoCodec ?? 'n/a'),
                _detail('Audio codec', asset.audioCodec ?? 'n/a'),
                _detail('Size', asset.sizeLabel),
                _detail('Path', asset.filePath),
                _detail('Status', asset.status ?? 'n/a'),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Close'),
            ),
          ],
        );
      },
    );
  }

  Widget _detail(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 110,
            child: Text(label, style: const TextStyle(color: AppTheme.textSecondary)),
          ),
          Expanded(child: SelectableText(value)),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final backend = ref.watch(backendConnectionProvider);
    final media = ref.watch(mediaListProvider);
    final projects = ref.watch(projectsProvider);
    final selectedProject = ref.watch(selectedProjectFilterProvider);

    return Padding(
      padding: const EdgeInsets.all(28),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SectionHeader(
            title: 'Video Library',
            subtitle: 'Import local MP4, MKV, and MOV files. Originals are never overwritten.',
          ),
          const SizedBox(height: 20),
          if (backend.state != BackendConnectionState.connected)
            Text(
              'Connect to the backend to manage media.',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: AppTheme.textSecondary,
                  ),
            )
          else ...[
            Wrap(
              spacing: 12,
              runSpacing: 12,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                SizedBox(
                  width: 280,
                  child: TextField(
                    controller: _searchController,
                    decoration: const InputDecoration(
                      prefixIcon: Icon(Icons.search),
                      hintText: 'Search videos…',
                    ),
                    onChanged: (value) {
                      ref.read(mediaSearchProvider.notifier).state = value;
                      ref.invalidate(mediaListProvider);
                    },
                  ),
                ),
                projects.when(
                  data: (items) {
                    return DropdownButton<String?>(
                      value: selectedProject,
                      hint: const Text('All projects'),
                      items: [
                        const DropdownMenuItem<String?>(
                          value: null,
                          child: Text('All projects'),
                        ),
                        for (final project in items)
                          DropdownMenuItem<String?>(
                            value: project.id,
                            child: Text(project.name),
                          ),
                      ],
                      onChanged: (value) {
                        ref.read(selectedProjectFilterProvider.notifier).state =
                            value;
                        ref.invalidate(mediaListProvider);
                      },
                    );
                  },
                  loading: () => const SizedBox(
                    width: 24,
                    height: 24,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
                  error: (e, _) => Text('$e'),
                ),
                FilledButton.icon(
                  onPressed: _busy ? null : _importVideos,
                  icon: const Icon(Icons.file_upload_outlined),
                  label: const Text('Import videos'),
                ),
                OutlinedButton.icon(
                  onPressed: _busy ? null : _createProject,
                  icon: const Icon(Icons.create_new_folder_outlined),
                  label: const Text('New project'),
                ),
                OutlinedButton.icon(
                  onPressed: _busy ? null : _batchProcessVisible,
                  icon: const Icon(Icons.playlist_play_outlined),
                  label: const Text('Batch process'),
                ),
                IconButton(
                  onPressed: _busy ? null : _refresh,
                  icon: const Icon(Icons.refresh),
                  tooltip: 'Refresh',
                ),
              ],
            ),
            if (_statusMessage != null) ...[
              const SizedBox(height: 12),
              Text(
                _statusMessage!,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: AppTheme.textSecondary,
                    ),
              ),
            ],
            if (_busy) ...[
              const SizedBox(height: 12),
              const LinearProgressIndicator(),
            ],
            const SizedBox(height: 20),
            Expanded(
              child: media.when(
                data: (items) {
                  if (items.isEmpty) {
                    return Center(
                      child: Text(
                        'No videos yet. Import local MP4, MKV, or MOV files.',
                        style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                              color: AppTheme.textSecondary,
                            ),
                      ),
                    );
                  }
                  return GridView.builder(
                    gridDelegate: const SliverGridDelegateWithMaxCrossAxisExtent(
                      maxCrossAxisExtent: 320,
                      mainAxisSpacing: 16,
                      crossAxisSpacing: 16,
                      childAspectRatio: 0.78,
                    ),
                    itemCount: items.length,
                    itemBuilder: (context, index) {
                      final asset = items[index];
                      return _MediaCard(
                        asset: asset,
                        token: ref.read(apiClientProvider).token,
                        onOpen: () => _showDetails(asset),
                        onReprocess: () => _reprocess(asset),
                        onTranscribe: () => _transcribe(asset),
                        onDelete: () => _delete(asset),
                      );
                    },
                  );
                },
                loading: () => const Center(child: CircularProgressIndicator()),
                error: (error, _) => Text(
                  'Failed to load library: $error',
                  style: const TextStyle(color: AppTheme.danger),
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _MediaCard extends StatelessWidget {
  const _MediaCard({
    required this.asset,
    required this.token,
    required this.onOpen,
    required this.onReprocess,
    required this.onTranscribe,
    required this.onDelete,
  });

  final MediaAsset asset;
  final String? token;
  final VoidCallback onOpen;
  final VoidCallback onReprocess;
  final VoidCallback onTranscribe;
  final VoidCallback onDelete;

  @override
  Widget build(BuildContext context) {
    final thumb = asset.thumbnailUrl == null
        ? null
        : 'http://${AppConfig.host}:${AppConfig.port}${asset.thumbnailUrl}';

    return Container(
      decoration: BoxDecoration(
        color: AppTheme.surfaceAlt,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.border),
      ),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onOpen,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Expanded(
              child: ColoredBox(
                color: AppTheme.surface,
                child: thumb == null
                    ? const Center(
                        child: Icon(Icons.movie_outlined, color: AppTheme.textSecondary),
                      )
                    : Image.network(
                        thumb,
                        fit: BoxFit.cover,
                        headers: {
                          if (token != null) 'X-API-Token': token!,
                        },
                        errorBuilder: (_, __, ___) => const Center(
                          child: Icon(Icons.broken_image_outlined),
                        ),
                      ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(12, 10, 8, 8),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    asset.originalFilename,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: Theme.of(context).textTheme.titleSmall?.copyWith(
                          fontWeight: FontWeight.w600,
                        ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    '${asset.durationLabel} · ${asset.resolutionLabel} · ${asset.sizeLabel}',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: AppTheme.textSecondary,
                        ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    '${asset.videoCodec ?? 'video'} / ${asset.audioCodec ?? 'audio'}',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: AppTheme.textSecondary,
                        ),
                  ),
                  Row(
                    children: [
                      IconButton(
                        tooltip: 'Reprocess metadata',
                        onPressed: onReprocess,
                        icon: const Icon(Icons.refresh, size: 18),
                      ),
                      IconButton(
                        tooltip: 'Queue transcription',
                        onPressed: onTranscribe,
                        icon: const Icon(Icons.graphic_eq, size: 18),
                      ),
                      IconButton(
                        tooltip: 'Remove',
                        onPressed: onDelete,
                        icon: const Icon(Icons.delete_outline, size: 18),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
