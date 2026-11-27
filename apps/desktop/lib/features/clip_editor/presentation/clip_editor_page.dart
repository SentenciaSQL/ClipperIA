import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/config/app_config.dart';
import '../../../core/services/backend_connection.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets/local_video_preview.dart';
import '../../../shared/widgets/section_header.dart';
import '../../exports/presentation/exports_page.dart';

class ClipEditorPage extends ConsumerStatefulWidget {
  const ClipEditorPage({super.key});

  @override
  ConsumerState<ClipEditorPage> createState() => _ClipEditorPageState();
}

class _ClipEditorPageState extends ConsumerState<ClipEditorPage> {
  String? _selectedClipId;
  double _start = 0;
  double _end = 15;
  String _aspect = '9:16';
  double _zoom = 1.0;
  String? _message;
  bool _busy = false;
  Map<String, dynamic>? _reframe;
  Map<String, dynamic>? _clipDetail;

  Future<void> _loadClip(String clipId) async {
    setState(() {
      _busy = true;
      _selectedClipId = clipId;
      _message = 'Loading clip…';
    });
    try {
      final detail = await ref.read(apiClientProvider).getClip(clipId);
      setState(() {
        _clipDetail = detail;
        _start = (detail['start_seconds'] as num?)?.toDouble() ?? 0;
        _end = (detail['end_seconds'] as num?)?.toDouble() ?? 15;
        _aspect = detail['aspect_ratio']?.toString() ?? '9:16';
        _message = null;
      });
    } catch (error) {
      setState(() => _message = 'Load failed: $error');
    } finally {
      setState(() => _busy = false);
    }
  }

  Future<void> _saveTimeline() async {
    if (_selectedClipId == null) return;
    setState(() => _busy = true);
    try {
      await ref.read(apiClientProvider).updateClip(_selectedClipId!, {
        'start_seconds': _start,
        'end_seconds': _end,
        'aspect_ratio': _aspect,
      });
      setState(() => _message = 'Timeline saved.');
      ref.invalidate(clipsProvider);
    } catch (error) {
      setState(() => _message = 'Save failed: $error');
    } finally {
      setState(() => _busy = false);
    }
  }

  Future<void> _generateCaptions() async {
    if (_selectedClipId == null) return;
    setState(() => _busy = true);
    try {
      final subs =
          await ref.read(apiClientProvider).generateSubtitles(_selectedClipId!);
      setState(
        () => _message =
            'Captions generated (${(subs['content'] as List?)?.length ?? 0} cues).',
      );
      await _loadClip(_selectedClipId!);
    } catch (error) {
      setState(() => _message = 'Caption generation failed: $error');
    } finally {
      setState(() => _busy = false);
    }
  }

  Future<void> _smartReframe() async {
    if (_selectedClipId == null) return;
    setState(() => _busy = true);
    try {
      final result =
          await ref.read(apiClientProvider).reframeClip(_selectedClipId!);
      setState(() {
        _reframe = result;
        _zoom = (result['zoom'] as num?)?.toDouble() ?? 1.2;
        _message =
            'Reframe ready (${result['method']}, faces=${result['detected_faces']}).';
      });
    } catch (error) {
      setState(() => _message = 'Reframe failed: $error');
    } finally {
      setState(() => _busy = false);
    }
  }

  Future<void> _render() async {
    if (_selectedClipId == null) return;
    setState(() => _busy = true);
    try {
      final settings = <String, dynamic>{
        'start_seconds': _start,
        'end_seconds': _end,
        'aspect_ratio': _aspect,
        'zoom': _zoom,
        if (_reframe?['crop_box'] != null) 'crop_box': _reframe!['crop_box'],
      };
      final subs = (_clipDetail?['subtitles'] as List?) ?? [];
      if (subs.isNotEmpty) {
        final path = (subs.first as Map)['file_path'];
        if (path != null) settings['subtitle_path'] = path;
      }
      final job = await ref.read(apiClientProvider).renderClip(
            _selectedClipId!,
            settings: settings,
          );
      setState(() => _message = 'Render queued: ${job['id']}');
    } catch (error) {
      setState(() => _message = 'Render failed: $error');
    } finally {
      setState(() => _busy = false);
    }
  }

  Future<void> _separateAudio() async {
    if (_selectedClipId == null) return;
    setState(() => _busy = true);
    try {
      final result =
          await ref.read(apiClientProvider).separateAudio(_selectedClipId!);
      setState(() => _message = 'Audio stems: ${result['stems']}');
    } catch (error) {
      setState(() => _message = 'Demucs unavailable or failed: $error');
    } finally {
      setState(() => _busy = false);
    }
  }

  Future<void> _generateMetadata() async {
    if (_selectedClipId == null) return;
    setState(() => _busy = true);
    try {
      final meta = await ref
          .read(apiClientProvider)
          .generateClipMetadata(_selectedClipId!);
      final tags = (meta['hashtags'] as List?)?.join(', ') ?? '';
      setState(
        () => _message =
            'Metadata: ${meta['title']} · #$tags · provider=${meta['provider']}',
      );
      await _loadClip(_selectedClipId!);
    } catch (error) {
      setState(() => _message = 'Metadata failed: $error');
    } finally {
      setState(() => _busy = false);
    }
  }

  Future<void> _altVersions() async {
    if (_selectedClipId == null) return;
    setState(() => _busy = true);
    try {
      final job = await ref
          .read(apiClientProvider)
          .generateAlternativeVersions(_selectedClipId!);
      setState(() => _message = 'Alt versions queued: ${job['id']}');
    } catch (error) {
      setState(() => _message = 'Alt versions failed: $error');
    } finally {
      setState(() => _busy = false);
    }
  }

  String _previewUrl({String? token}) {
    final base =
        'http://${AppConfig.host}:${AppConfig.port}/api/v1/clips/$_selectedClipId/file';
    if (token == null || token.isEmpty) return base;
    return '$base?token=${Uri.encodeQueryComponent(token)}';
  }

  Future<void> _copy(String value, String label) async {
    await Clipboard.setData(ClipboardData(text: value));
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('$label copied'), duration: const Duration(seconds: 2)),
    );
  }

  @override
  Widget build(BuildContext context) {
    final backend = ref.watch(backendConnectionProvider);
    final clips = ref.watch(clipsProvider);
    final token = ref.watch(apiClientProvider).token;
    final filePath = _clipDetail?['file_path']?.toString();
    final browserUrl = _previewUrl(token: token);

    return Padding(
      padding: const EdgeInsets.all(28),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SectionHeader(
            title: 'Clip Editor',
            subtitle: 'Timeline, captions, smart reframing, zoom, and alternate audio.',
          ),
          const SizedBox(height: 16),
          if (backend.state != BackendConnectionState.connected)
            const Text('Connect to the backend to edit clips.')
          else ...[
            clips.when(
              data: (items) {
                if (items.isEmpty) {
                  return const Text(
                    'No clips yet. Generate clips in Export Center first.',
                    style: TextStyle(color: AppTheme.textSecondary),
                  );
                }
                return DropdownButton<String>(
                  value: _selectedClipId,
                  hint: const Text('Select clip'),
                  items: [
                    for (final clip in items)
                      DropdownMenuItem(
                        value: clip['id'] as String,
                        child: Text(clip['title']?.toString() ?? clip['id']),
                      ),
                  ],
                  onChanged: (id) {
                    if (id != null) _loadClip(id);
                  },
                );
              },
              loading: () => const LinearProgressIndicator(),
              error: (e, _) => Text('$e'),
            ),
            if (_message != null) ...[
              const SizedBox(height: 8),
              Text(_message!, style: const TextStyle(color: AppTheme.textSecondary)),
            ],
            if (_selectedClipId != null) ...[
              const SizedBox(height: 16),
              Expanded(
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      flex: 3,
                      child: Container(
                        decoration: BoxDecoration(
                          color: AppTheme.surfaceAlt,
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(color: AppTheme.border),
                        ),
                        clipBehavior: Clip.antiAlias,
                        child: Column(
                          children: [
                            Expanded(
                              child: LocalVideoPreview(
                                key: ValueKey(filePath ?? _selectedClipId),
                                filePath: filePath,
                                networkUrl: browserUrl,
                              ),
                            ),
                            Padding(
                              padding: const EdgeInsets.fromLTRB(12, 8, 12, 12),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Row(
                                    children: [
                                      Expanded(
                                        child: SelectableText(
                                          browserUrl,
                                          style: Theme.of(context).textTheme.bodySmall,
                                        ),
                                      ),
                                      IconButton(
                                        tooltip: 'Copy browser URL (includes token)',
                                        onPressed: () =>
                                            _copy(browserUrl, 'Preview URL'),
                                        icon: const Icon(Icons.link, size: 16),
                                      ),
                                      if (filePath != null && filePath.isNotEmpty)
                                        IconButton(
                                          tooltip: 'Copy local file path',
                                          onPressed: () =>
                                              _copy(filePath, 'Local file path'),
                                          icon: const Icon(Icons.folder_open, size: 16),
                                        ),
                                    ],
                                  ),
                                  if (filePath != null && filePath.isNotEmpty)
                                    SelectableText(
                                      filePath,
                                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                            color: AppTheme.textSecondary,
                                          ),
                                    ),
                                ],
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(width: 16),
                    Expanded(
                      flex: 2,
                      child: ListView(
                        children: [
                          Text('Timeline', style: Theme.of(context).textTheme.titleMedium),
                          Text('Start ${_start.toStringAsFixed(1)}s'),
                          Slider(
                            value: _start,
                            min: 0,
                            max: (_end - 1).clamp(1, 600),
                            onChanged: (v) => setState(() => _start = v),
                          ),
                          Text('End ${_end.toStringAsFixed(1)}s'),
                          Slider(
                            value: _end,
                            min: (_start + 1).clamp(1, 600),
                            max: 600,
                            onChanged: (v) => setState(() => _end = v),
                          ),
                          const SizedBox(height: 8),
                          DropdownButtonFormField<String>(
                            value: _aspect,
                            decoration: const InputDecoration(labelText: 'Aspect ratio'),
                            items: const [
                              DropdownMenuItem(value: '9:16', child: Text('9:16')),
                              DropdownMenuItem(value: '16:9', child: Text('16:9')),
                              DropdownMenuItem(value: '1:1', child: Text('1:1')),
                            ],
                            onChanged: (v) => setState(() => _aspect = v ?? '9:16'),
                          ),
                          const SizedBox(height: 8),
                          Text('Zoom ${_zoom.toStringAsFixed(2)}x'),
                          Slider(
                            value: _zoom,
                            min: 1,
                            max: 2.5,
                            onChanged: (v) => setState(() => _zoom = v),
                          ),
                          const SizedBox(height: 12),
                          Wrap(
                            spacing: 8,
                            runSpacing: 8,
                            children: [
                              OutlinedButton(
                                onPressed: _busy ? null : _saveTimeline,
                                child: const Text('Save timeline'),
                              ),
                              OutlinedButton(
                                onPressed: _busy ? null : _generateCaptions,
                                child: const Text('Captions'),
                              ),
                              OutlinedButton(
                                onPressed: _busy ? null : _smartReframe,
                                child: const Text('Smart reframe'),
                              ),
                              OutlinedButton(
                                onPressed: _busy ? null : _separateAudio,
                                child: const Text('Demucs audio'),
                              ),
                              OutlinedButton(
                                onPressed: _busy ? null : _generateMetadata,
                                child: const Text('AI description'),
                              ),
                              OutlinedButton(
                                onPressed: _busy ? null : _altVersions,
                                child: const Text('Alt ratios'),
                              ),
                              FilledButton(
                                onPressed: _busy ? null : _render,
                                child: const Text('Render version'),
                              ),
                            ],
                          ),
                          if (_reframe != null) ...[
                            const SizedBox(height: 12),
                            Text(
                              'Crop: ${_reframe!['crop_box']}',
                              style: const TextStyle(color: AppTheme.textSecondary),
                            ),
                          ],
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ],
        ],
      ),
    );
  }
}
