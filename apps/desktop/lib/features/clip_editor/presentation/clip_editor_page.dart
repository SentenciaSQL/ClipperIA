import 'package:file_picker/file_picker.dart';
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

class _ClipEditorPageState extends ConsumerState<ClipEditorPage>
    with SingleTickerProviderStateMixin {
  String? _selectedClipId;
  double _start = 0;
  double _end = 15;
  String _aspect = '9:16';
  double _zoom = 1.0;
  double _opacity = 1.0;
  double _masterVolume = 1.0;
  String? _message;
  bool _busy = false;
  Map<String, dynamic>? _reframe;
  Map<String, dynamic>? _clipDetail;
  Map<String, dynamic>? _editorState;
  List<Map<String, dynamic>> _tracks = [];
  List<Map<String, dynamic>> _cues = [];
  String? _subtitleId;
  String _captionPreset = 'classic';
  int? _selectedCueIndex;
  late final TabController _tabs;

  @override
  void initState() {
    super.initState();
    _tabs = TabController(length: 4, vsync: this);
  }

  @override
  void dispose() {
    _tabs.dispose();
    super.dispose();
  }

  Future<void> _loadClip(String clipId) async {
    setState(() {
      _busy = true;
      _selectedClipId = clipId;
      _message = 'Loading clip…';
    });
    try {
      final api = ref.read(apiClientProvider);
      final detail = await api.getClip(clipId);
      final editor = await api.getClipEditor(clipId);
      final editorMap =
          (editor['editor'] as Map?)?.cast<String, dynamic>() ?? {};
      final subs = (detail['subtitles'] as List?) ?? [];
      final firstSub = subs.isNotEmpty ? Map<String, dynamic>.from(subs.first as Map) : null;
      setState(() {
        _clipDetail = detail;
        _editorState = editor;
        _tracks = ((editor['audio_tracks'] as List?) ?? [])
            .map((e) => Map<String, dynamic>.from(e as Map))
            .toList();
        _start = (detail['start_seconds'] as num?)?.toDouble() ?? 0;
        _end = (detail['end_seconds'] as num?)?.toDouble() ?? 15;
        _aspect = detail['aspect_ratio']?.toString() ?? '9:16';
        _zoom = (editorMap['zoom'] as num?)?.toDouble() ?? 1.0;
        _opacity = (editorMap['opacity'] as num?)?.toDouble() ?? 1.0;
        _masterVolume = (editorMap['master_volume'] as num?)?.toDouble() ?? 1.0;
        _captionPreset = editorMap['caption_preset']?.toString() ?? 'classic';
        _subtitleId = firstSub?['id']?.toString();
        _cues = ((firstSub?['content'] as List?) ?? [])
            .map((e) => Map<String, dynamic>.from(e as Map))
            .toList();
        _message = null;
      });
    } catch (error) {
      setState(() => _message = 'Load failed: $error');
    } finally {
      setState(() => _busy = false);
    }
  }

  Future<void> _persistEditor(Map<String, dynamic> patch) async {
    if (_selectedClipId == null) return;
    final editor = await ref.read(apiClientProvider).patchClipEditor(
          _selectedClipId!,
          patch,
        );
    setState(() {
      _editorState = editor;
      _tracks = ((editor['audio_tracks'] as List?) ?? [])
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList();
    });
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
      await _persistEditor({
        'zoom': _zoom,
        'opacity': _opacity,
        'master_volume': _masterVolume,
        'caption_preset': _captionPreset,
        if (_reframe?['crop_box'] != null) 'crop_box': _reframe!['crop_box'],
      });
      setState(() => _message = 'Timeline + editor state saved.');
      ref.invalidate(clipsProvider);
    } catch (error) {
      setState(() => _message = 'Save failed: $error');
    } finally {
      setState(() => _busy = false);
    }
  }

  Future<void> _generateCaptions({bool replace = false}) async {
    if (_selectedClipId == null) return;
    setState(() => _busy = true);
    try {
      final subs = await ref.read(apiClientProvider).generateSubtitlesAdvanced(
            _selectedClipId!,
            preset: _captionPreset,
            replaceExisting: replace,
          );
      setState(() {
        _subtitleId = subs['id']?.toString();
        _cues = ((subs['content'] as List?) ?? [])
            .map((e) => Map<String, dynamic>.from(e as Map))
            .toList();
        _message =
            'Captions ready (${_cues.length} cues, preset=$_captionPreset).';
      });
      await _loadClip(_selectedClipId!);
    } catch (error) {
      setState(() => _message = 'Caption generation failed: $error');
    } finally {
      setState(() => _busy = false);
    }
  }

  Future<void> _saveCaptions() async {
    if (_subtitleId == null) return;
    setState(() => _busy = true);
    try {
      await ref.read(apiClientProvider).updateSubtitlesAdvanced(
            _subtitleId!,
            cues: _cues,
            preset: _captionPreset,
          );
      setState(() => _message = 'Captions saved (ASS regenerated).');
    } catch (error) {
      setState(() => _message = 'Caption save failed: $error');
    } finally {
      setState(() => _busy = false);
    }
  }

  Future<void> _applyWordOverride(String phrase, String hexColor) async {
    if (_subtitleId == null || _selectedCueIndex == null) return;
    final cue = _cues[_selectedCueIndex!];
    final text = cue['text']?.toString() ?? '';
    final start = text.indexOf(phrase);
    if (start < 0) {
      setState(() => _message = 'Phrase "$phrase" not found in selected cue.');
      return;
    }
    setState(() => _busy = true);
    try {
      final updated = await ref.read(apiClientProvider).addCaptionWordOverride(
            _subtitleId!,
            cueIndex: _selectedCueIndex!,
            override: {
              'start_char': start,
              'end_char': start + phrase.length,
              'text': phrase,
              'style': {'color': hexColor, 'bold': true, 'font_size': 56},
            },
          );
      setState(() {
        _cues = ((updated['content'] as List?) ?? [])
            .map((e) => Map<String, dynamic>.from(e as Map))
            .toList();
        _message = 'Override applied to "$phrase".';
      });
    } catch (error) {
      setState(() => _message = 'Override failed: $error');
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
      await _persistEditor({
        'zoom': _zoom,
        if (result['crop_box'] != null) 'crop_box': result['crop_box'],
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
      await _saveTimeline();
      if (_subtitleId != null && _cues.isNotEmpty) {
        await _saveCaptions();
      }
      final settings = <String, dynamic>{
        'start_seconds': _start,
        'end_seconds': _end,
        'aspect_ratio': _aspect,
        'zoom': _zoom,
        'opacity': _opacity,
        'master_volume': _masterVolume,
        'burn_captions': true,
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
      final job =
          await ref.read(apiClientProvider).separateAudio(_selectedClipId!);
      setState(
        () => _message =
            'Demucs job ${job['id']} queued. Stems appear as audio tracks when completed. If you get 501: pip install demucs',
      );
    } catch (error) {
      setState(() => _message = 'Demucs unavailable or failed: $error');
    } finally {
      setState(() => _busy = false);
    }
  }

  Future<void> _importAudio() async {
    if (_selectedClipId == null) return;
    final result = await FilePicker.pickFiles(
      type: FileType.custom,
      allowedExtensions: const ['mp3', 'wav', 'aac', 'm4a', 'flac', 'ogg'],
    );
    if (result == null || result.files.isEmpty) return;
    final path = result.files.first.path;
    if (path == null) return;
    setState(() => _busy = true);
    try {
      await ref.read(apiClientProvider).importAudioTrack(
            _selectedClipId!,
            path: path,
            name: result.files.first.name,
            kind: 'music',
          );
      await _loadClip(_selectedClipId!);
      setState(() => _message = 'Audio track imported.');
    } catch (error) {
      setState(() => _message = 'Audio import failed: $error');
    } finally {
      setState(() => _busy = false);
    }
  }

  Future<void> _updateTrack(String id, Map<String, dynamic> patch) async {
    try {
      await ref.read(apiClientProvider).updateAudioTrack(id, patch);
      if (_selectedClipId != null) await _loadClip(_selectedClipId!);
    } catch (error) {
      setState(() => _message = 'Track update failed: $error');
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
            subtitle:
                'Multi-track audio, captions with word overrides, and independent video opacity.',
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
            if (_busy) const LinearProgressIndicator(),
            if (_selectedClipId != null) ...[
              const SizedBox(height: 12),
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
                              child: Opacity(
                                opacity: _opacity.clamp(0.05, 1.0),
                                child: LocalVideoPreview(
                                  key: ValueKey('${filePath}_$_opacity'),
                                  filePath: filePath,
                                  networkUrl: browserUrl,
                                ),
                              ),
                            ),
                            // Caption overlay preview (independent of video opacity)
                            if (_cues.isNotEmpty)
                              Container(
                                width: double.infinity,
                                color: Colors.transparent,
                                padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
                                child: Text(
                                  _cues.first['text']?.toString() ?? '',
                                  textAlign: TextAlign.center,
                                  style: TextStyle(
                                    color: Colors.white.withOpacity(1.0),
                                    fontWeight: FontWeight.w700,
                                    fontSize: 18,
                                    shadows: const [
                                      Shadow(blurRadius: 4, color: Colors.black),
                                    ],
                                  ),
                                ),
                              ),
                            Padding(
                              padding: const EdgeInsets.fromLTRB(12, 4, 12, 10),
                              child: Row(
                                children: [
                                  Expanded(
                                    child: SelectableText(
                                      browserUrl,
                                      style: Theme.of(context).textTheme.bodySmall,
                                    ),
                                  ),
                                  IconButton(
                                    tooltip: 'Copy browser URL',
                                    onPressed: () => _copy(browserUrl, 'Preview URL'),
                                    icon: const Icon(Icons.link, size: 16),
                                  ),
                                  if (filePath != null)
                                    IconButton(
                                      tooltip: 'Copy file path',
                                      onPressed: () =>
                                          _copy(filePath, 'Local file path'),
                                      icon: const Icon(Icons.folder_open, size: 16),
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
                      flex: 3,
                      child: Column(
                        children: [
                          TabBar(
                            controller: _tabs,
                            labelColor: AppTheme.accent,
                            unselectedLabelColor: AppTheme.textSecondary,
                            tabs: const [
                              Tab(text: 'Timeline'),
                              Tab(text: 'Audio'),
                              Tab(text: 'Captions'),
                              Tab(text: 'Opacity'),
                            ],
                          ),
                          Expanded(
                            child: TabBarView(
                              controller: _tabs,
                              children: [
                                _buildTimelineTab(),
                                _buildAudioTab(),
                                _buildCaptionsTab(),
                                _buildOpacityTab(),
                              ],
                            ),
                          ),
                          const SizedBox(height: 8),
                          Row(
                            children: [
                              FilledButton(
                                onPressed: _busy ? null : _render,
                                child: const Text('Render version'),
                              ),
                              const SizedBox(width: 8),
                              OutlinedButton(
                                onPressed: _busy ? null : _saveTimeline,
                                child: const Text('Save all'),
                              ),
                            ],
                          ),
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

  Widget _buildTimelineTab() {
    return ListView(
      padding: const EdgeInsets.only(top: 12),
      children: [
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
        Text('Zoom ${_zoom.toStringAsFixed(2)}x'),
        Slider(
          value: _zoom,
          min: 1,
          max: 2.5,
          onChanged: (v) => setState(() => _zoom = v),
        ),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            OutlinedButton(
              onPressed: _busy ? null : _smartReframe,
              child: const Text('Smart reframe'),
            ),
            OutlinedButton(
              onPressed: _busy ? null : _separateAudio,
              child: const Text('Demucs stems'),
            ),
          ],
        ),
        const SizedBox(height: 12),
        Text(
          'Tracks on timeline',
          style: Theme.of(context).textTheme.titleSmall,
        ),
        const SizedBox(height: 6),
        for (final track in _tracks)
          Container(
            margin: const EdgeInsets.only(bottom: 6),
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: AppTheme.surface,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: AppTheme.border),
            ),
            child: Text(
              '${track['kind']} · ${track['name']} · '
              '${track['muted'] == true ? 'muted' : 'vol ${(track['volume'] as num?)?.toStringAsFixed(2)}'} · '
              '@${(track['start_seconds'] as num?)?.toStringAsFixed(1)}s',
              style: const TextStyle(color: AppTheme.textSecondary),
            ),
          ),
      ],
    );
  }

  Widget _buildAudioTab() {
    return ListView(
      padding: const EdgeInsets.only(top: 12),
      children: [
        Text('Master volume ${(_masterVolume * 100).round()}%'),
        Slider(
          value: _masterVolume,
          min: 0,
          max: 2,
          onChanged: (v) => setState(() => _masterVolume = v),
          onChangeEnd: (v) => _persistEditor({'master_volume': v}),
        ),
        Wrap(
          spacing: 8,
          children: [
            OutlinedButton.icon(
              onPressed: _busy ? null : _importAudio,
              icon: const Icon(Icons.library_music),
              label: const Text('Import audio'),
            ),
            OutlinedButton.icon(
              onPressed: _busy ? null : _separateAudio,
              icon: const Icon(Icons.call_split),
              label: const Text('Separate stems'),
            ),
          ],
        ),
        const SizedBox(height: 12),
        for (final track in _tracks)
          Container(
            margin: const EdgeInsets.only(bottom: 10),
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: AppTheme.surface,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: AppTheme.border),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        '${track['name']} (${track['kind']})',
                        style: const TextStyle(fontWeight: FontWeight.w600),
                      ),
                    ),
                    Switch(
                      value: track['enabled'] != false,
                      onChanged: (v) =>
                          _updateTrack(track['id'] as String, {'enabled': v}),
                    ),
                  ],
                ),
                Row(
                  children: [
                    FilterChip(
                      label: Text(track['muted'] == true ? 'Muted' : 'Audible'),
                      selected: track['muted'] == true,
                      onSelected: (v) =>
                          _updateTrack(track['id'] as String, {'muted': v}),
                    ),
                    const SizedBox(width: 8),
                    FilterChip(
                      label: Text(
                        track['exclude_from_export'] == true
                            ? 'Exclude export'
                            : 'In export',
                      ),
                      selected: track['exclude_from_export'] == true,
                      onSelected: (v) => _updateTrack(
                        track['id'] as String,
                        {'exclude_from_export': v},
                      ),
                    ),
                  ],
                ),
                Text(
                  'Volume ${(((track['volume'] as num?)?.toDouble() ?? 1) * 100).round()}%',
                ),
                Slider(
                  value: ((track['volume'] as num?)?.toDouble() ?? 1).clamp(0, 2),
                  min: 0,
                  max: 2,
                  onChangeEnd: (v) =>
                      _updateTrack(track['id'] as String, {'volume': v}),
                  onChanged: (_) {},
                ),
                Text(
                  'Start on timeline ${(track['start_seconds'] as num?)?.toStringAsFixed(1) ?? '0'}s',
                ),
                Slider(
                  value: ((track['start_seconds'] as num?)?.toDouble() ?? 0)
                      .clamp(0, 120),
                  min: 0,
                  max: 120,
                  onChangeEnd: (v) =>
                      _updateTrack(track['id'] as String, {'start_seconds': v}),
                  onChanged: (_) {},
                ),
                if (track['kind'] != 'original')
                  Align(
                    alignment: Alignment.centerRight,
                    child: TextButton(
                      onPressed: () async {
                        await ref
                            .read(apiClientProvider)
                            .deleteAudioTrack(track['id'] as String);
                        if (_selectedClipId != null) {
                          await _loadClip(_selectedClipId!);
                        }
                      },
                      child: const Text('Delete'),
                    ),
                  ),
              ],
            ),
          ),
      ],
    );
  }

  Widget _buildCaptionsTab() {
    return ListView(
      padding: const EdgeInsets.only(top: 12),
      children: [
        DropdownButtonFormField<String>(
          value: _captionPreset,
          decoration: const InputDecoration(labelText: 'Style preset'),
          items: const [
            DropdownMenuItem(value: 'classic', child: Text('Classic')),
            DropdownMenuItem(value: 'modern', child: Text('Modern')),
            DropdownMenuItem(value: 'tiktok', child: Text('TikTok')),
            DropdownMenuItem(value: 'youtube_shorts', child: Text('YouTube Shorts')),
            DropdownMenuItem(value: 'karaoke', child: Text('Karaoke')),
            DropdownMenuItem(value: 'minimal', child: Text('Minimal')),
            DropdownMenuItem(value: 'bold', child: Text('Bold')),
            DropdownMenuItem(value: 'highlight', child: Text('Highlight')),
            DropdownMenuItem(value: 'neon', child: Text('Neon')),
            DropdownMenuItem(value: 'custom', child: Text('Custom')),
          ],
          onChanged: (v) {
            setState(() => _captionPreset = v ?? 'classic');
            _persistEditor({'caption_preset': _captionPreset});
          },
        ),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          children: [
            OutlinedButton(
              onPressed: _busy ? null : () => _generateCaptions(),
              child: const Text('Generate / keep edits'),
            ),
            OutlinedButton(
              onPressed: _busy ? null : () => _generateCaptions(replace: true),
              child: const Text('Regenerate replace'),
            ),
            FilledButton.tonal(
              onPressed: _busy ? null : _saveCaptions,
              child: const Text('Save captions'),
            ),
          ],
        ),
        const SizedBox(height: 12),
        if (_cues.isEmpty)
          const Text(
            'No captions yet.',
            style: TextStyle(color: AppTheme.textSecondary),
          ),
        for (var i = 0; i < _cues.length; i++)
          Container(
            margin: const EdgeInsets.only(bottom: 8),
            decoration: BoxDecoration(
              color: _selectedCueIndex == i
                  ? AppTheme.accent.withOpacity(0.08)
                  : AppTheme.surface,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(
                color: _selectedCueIndex == i ? AppTheme.accent : AppTheme.border,
              ),
            ),
            child: ListTile(
              dense: true,
              title: TextField(
                controller: TextEditingController(
                  text: _cues[i]['text']?.toString() ?? '',
                ),
                maxLines: 2,
                style: const TextStyle(fontSize: 13),
                decoration: const InputDecoration(
                  border: InputBorder.none,
                  isDense: true,
                ),
                onChanged: (v) => _cues[i]['text'] = v,
                onTap: () => setState(() => _selectedCueIndex = i),
              ),
              subtitle: Text(
                '${(_cues[i]['start'] as num?)?.toStringAsFixed(1)}s → '
                '${(_cues[i]['end'] as num?)?.toStringAsFixed(1)}s'
                '${((_cues[i]['overrides'] as List?)?.isNotEmpty ?? false) ? ' · overrides' : ''}',
                style: const TextStyle(color: AppTheme.textSecondary, fontSize: 11),
              ),
              onTap: () => setState(() => _selectedCueIndex = i),
            ),
          ),
        if (_selectedCueIndex != null) ...[
          const SizedBox(height: 8),
          Text('Word override on selected cue', style: Theme.of(context).textTheme.titleSmall),
          Wrap(
            spacing: 8,
            children: [
              OutlinedButton(
                onPressed: () {
                  final text = _cues[_selectedCueIndex!]['text']?.toString() ?? '';
                  final words = text.split(RegExp(r'\s+')).where((w) => w.length > 3);
                  if (words.isEmpty) return;
                  _applyWordOverride(words.first.replaceAll(RegExp(r'[^\w]'), ''), '#FFD400');
                },
                child: const Text('Highlight first long word (yellow)'),
              ),
            ],
          ),
        ],
      ],
    );
  }

  Widget _buildOpacityTab() {
    final keyframes =
        (((_editorState?['editor'] as Map?)?['opacity_keyframes'] as List?) ?? [])
            .map((e) => Map<String, dynamic>.from(e as Map))
            .toList();
    return ListView(
      padding: const EdgeInsets.only(top: 12),
      children: [
        Text(
          'Video opacity ${(_opacity * 100).round()}%',
          style: Theme.of(context).textTheme.titleSmall,
        ),
        const Text(
          'Captions stay at full opacity — composition uses separate layers.',
          style: TextStyle(color: AppTheme.textSecondary),
        ),
        Slider(
          value: _opacity,
          min: 0,
          max: 1,
          onChanged: (v) => setState(() => _opacity = v),
          onChangeEnd: (v) => _persistEditor({'opacity': v}),
        ),
        Wrap(
          spacing: 8,
          children: [
            OutlinedButton(
              onPressed: () {
                setState(() => _opacity = 1);
                _persistEditor({'opacity': 1.0, 'opacity_keyframes': []});
              },
              child: const Text('Reset 100%'),
            ),
            OutlinedButton(
              onPressed: () {
                setState(() => _opacity = 0.4);
                _persistEditor({
                  'opacity': 0.4,
                  'opacity_keyframes': [
                    {'t': 0.0, 'opacity': 1.0},
                    {'t': 3.0, 'opacity': 0.5},
                    {'t': 6.0, 'opacity': 0.25},
                    {'t': 9.0, 'opacity': 1.0},
                  ],
                });
                setState(() => _message = 'Example opacity keyframes applied.');
              },
              child: const Text('Example keyframes'),
            ),
          ],
        ),
        const SizedBox(height: 12),
        Text('Keyframes', style: Theme.of(context).textTheme.titleSmall),
        if (keyframes.isEmpty)
          const Text(
            'No keyframes — constant opacity is used.',
            style: TextStyle(color: AppTheme.textSecondary),
          ),
        for (final kf in keyframes)
          Text(
            't=${(kf['t'] as num?)?.toStringAsFixed(1)}s → '
            '${(((kf['opacity'] as num?)?.toDouble() ?? 1) * 100).round()}%',
            style: const TextStyle(color: AppTheme.textSecondary),
          ),
      ],
    );
  }
}
