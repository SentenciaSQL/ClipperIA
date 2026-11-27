import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/services/backend_connection.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets/section_header.dart';
import '../../video_library/presentation/video_library_providers.dart'
    show mediaListProvider;

final clipsProvider = FutureProvider<List<Map<String, dynamic>>>((ref) async {
  final status = ref.watch(backendConnectionProvider);
  if (status.state != BackendConnectionState.connected) return [];
  return ref.watch(apiClientProvider).listClips();
});

final exportsProvider = FutureProvider<List<Map<String, dynamic>>>((ref) async {
  final status = ref.watch(backendConnectionProvider);
  if (status.state != BackendConnectionState.connected) return [];
  return ref.watch(apiClientProvider).listExports();
});

class ExportsPage extends ConsumerStatefulWidget {
  const ExportsPage({super.key});

  @override
  ConsumerState<ExportsPage> createState() => _ExportsPageState();
}

class _ExportsPageState extends ConsumerState<ExportsPage> {
  String _preset = 'tiktok';
  String _aspect = '9:16';
  double _duration = 30;
  String? _message;
  bool _busy = false;

  Future<void> _generate() async {
    final media = await ref.read(mediaListProvider.future);
    if (media.isEmpty) {
      setState(() => _message = 'Import a video and detect highlights first.');
      return;
    }
    setState(() {
      _busy = true;
      _message = 'Queueing clip generation…';
    });
    try {
      final job = await ref.read(apiClientProvider).generateClips(
            mediaId: media.first.id,
            aspectRatio: _aspect,
            maxDuration: _duration,
          );
      setState(() => _message = 'Job ${job['id']} queued (${job['status']}).');
      await Future<void>.delayed(const Duration(seconds: 2));
      ref.invalidate(clipsProvider);
      ref.invalidate(dashboardOverviewProvider);
    } catch (error) {
      setState(() => _message = 'Generate failed: $error');
    } finally {
      setState(() => _busy = false);
    }
  }

  Future<void> _export(String clipId) async {
    setState(() {
      _busy = true;
      _message = 'Queueing export ($_preset)…';
    });
    try {
      final job = await ref
          .read(apiClientProvider)
          .exportClip(clipId, preset: _preset);
      setState(() => _message = 'Export job ${job['id']} queued.');
      await Future<void>.delayed(const Duration(seconds: 2));
      ref.invalidate(exportsProvider);
    } catch (error) {
      setState(() => _message = 'Export failed: $error');
    } finally {
      setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final backend = ref.watch(backendConnectionProvider);
    final clips = ref.watch(clipsProvider);
    final exports = ref.watch(exportsProvider);

    return Padding(
      padding: const EdgeInsets.all(28),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SectionHeader(
            title: 'Export Center',
            subtitle: 'Generate clips from highlights and export TikTok / Reels / Shorts presets.',
          ),
          const SizedBox(height: 16),
          if (backend.state != BackendConnectionState.connected)
            const Text('Connect to the backend to manage exports.')
          else ...[
            Wrap(
              spacing: 12,
              runSpacing: 12,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                DropdownButton<String>(
                  value: _aspect,
                  items: const [
                    DropdownMenuItem(value: '9:16', child: Text('9:16')),
                    DropdownMenuItem(value: '16:9', child: Text('16:9')),
                    DropdownMenuItem(value: '1:1', child: Text('1:1')),
                  ],
                  onChanged: (v) => setState(() => _aspect = v ?? '9:16'),
                ),
                DropdownButton<double>(
                  value: _duration,
                  items: const [
                    DropdownMenuItem(value: 12, child: Text('12s')),
                    DropdownMenuItem(value: 15, child: Text('15s')),
                    DropdownMenuItem(value: 20, child: Text('20s')),
                    DropdownMenuItem(value: 30, child: Text('30s')),
                    DropdownMenuItem(value: 45, child: Text('45s')),
                    DropdownMenuItem(value: 60, child: Text('60s')),
                    DropdownMenuItem(value: 90, child: Text('90s')),
                  ],
                  onChanged: (v) => setState(() => _duration = v ?? 30),
                ),
                DropdownButton<String>(
                  value: _preset,
                  items: const [
                    DropdownMenuItem(value: 'tiktok', child: Text('TikTok')),
                    DropdownMenuItem(value: 'instagram_reels', child: Text('Reels')),
                    DropdownMenuItem(value: 'youtube_shorts', child: Text('Shorts')),
                    DropdownMenuItem(value: 'landscape', child: Text('16:9')),
                    DropdownMenuItem(value: 'square', child: Text('1:1')),
                  ],
                  onChanged: (v) => setState(() => _preset = v ?? 'tiktok'),
                ),
                FilledButton.icon(
                  onPressed: _busy ? null : _generate,
                  icon: const Icon(Icons.movie_creation_outlined),
                  label: const Text('Generate clips from highlights'),
                ),
                IconButton(
                  onPressed: () {
                    ref.invalidate(clipsProvider);
                    ref.invalidate(exportsProvider);
                  },
                  icon: const Icon(Icons.refresh),
                ),
              ],
            ),
            if (_message != null) ...[
              const SizedBox(height: 8),
              Text(_message!, style: const TextStyle(color: AppTheme.textSecondary)),
            ],
            const SizedBox(height: 16),
            Expanded(
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: clips.when(
                      data: (items) {
                        if (items.isEmpty) {
                          return const Text(
                            'No clips yet.',
                            style: TextStyle(color: AppTheme.textSecondary),
                          );
                        }
                        return ListView.separated(
                          itemCount: items.length,
                          separatorBuilder: (_, __) => const SizedBox(height: 8),
                          itemBuilder: (context, index) {
                            final clip = items[index];
                            return Container(
                              padding: const EdgeInsets.all(14),
                              decoration: BoxDecoration(
                                color: AppTheme.surfaceAlt,
                                borderRadius: BorderRadius.circular(12),
                                border: Border.all(color: AppTheme.border),
                              ),
                              child: Row(
                                children: [
                                  Expanded(
                                    child: Column(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: [
                                        Text(
                                          clip['title']?.toString() ?? 'Clip',
                                          style: const TextStyle(fontWeight: FontWeight.w600),
                                        ),
                                        Text(
                                          '${clip['start_seconds']}s → ${clip['end_seconds']}s · ${clip['aspect_ratio']} · ${clip['status']}',
                                          style: const TextStyle(color: AppTheme.textSecondary),
                                        ),
                                      ],
                                    ),
                                  ),
                                  FilledButton(
                                    onPressed: _busy
                                        ? null
                                        : () => _export(clip['id'] as String),
                                    child: const Text('Export'),
                                  ),
                                ],
                              ),
                            );
                          },
                        );
                      },
                      loading: () => const Center(child: CircularProgressIndicator()),
                      error: (e, _) => Text('$e'),
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: exports.when(
                      data: (items) {
                        return ListView(
                          children: [
                            Text('Exports', style: Theme.of(context).textTheme.titleMedium),
                            const SizedBox(height: 8),
                            if (items.isEmpty)
                              const Text(
                                'No exports yet.',
                                style: TextStyle(color: AppTheme.textSecondary),
                              ),
                            for (final item in items)
                              ListTile(
                                contentPadding: EdgeInsets.zero,
                                title: Text('${item['preset']} · ${item['resolution']}'),
                                subtitle: Text('${item['status']} · ${item['id']}'),
                              ),
                          ],
                        );
                      },
                      loading: () => const Center(child: CircularProgressIndicator()),
                      error: (e, _) => Text('$e'),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}
