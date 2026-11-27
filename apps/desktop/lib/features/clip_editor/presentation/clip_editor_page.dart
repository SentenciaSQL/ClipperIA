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
import 'caption_overlay.dart';
import 'caption_style_editor.dart';
import 'caption_style_preview.dart';

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
  Map<String, dynamic> _presets = {};
  Map<String, dynamic> _systemPresets = {};
  Map<String, dynamic> _customPresets = {};
  Map<String, dynamic> _captionStyle = {};
  Map<String, dynamic>? _captionSync;
  Map<String, dynamic>? _captionDraft;
  String? _voiceTrackId;
  String _correctionFind = '';
  String _correctionReplace = '';
  bool _captionSelected = true;
  final Map<String, TextEditingController> _offsetControllers = {};
  late final TabController _tabs;

  @override
  void initState() {
    super.initState();
    _tabs = TabController(length: 4, vsync: this);
  }

  @override
  void dispose() {
    _tabs.dispose();
    for (final c in _offsetControllers.values) {
      c.dispose();
    }
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
      final sync = (editor['caption_sync'] as Map?)?.cast<String, dynamic>();
      final presetsPayload =
          (editor['caption_presets'] as Map?)?.cast<String, dynamic>() ?? {};
      final allPresets = _flattenPresets(presetsPayload);
      final system =
          (presetsPayload['system'] as Map?)?.cast<String, dynamic>() ?? {};
      final custom =
          (presetsPayload['custom'] as Map?)?.cast<String, dynamic>() ?? {};
      final subs = (editor['subtitles'] as List?) ??
          (detail['subtitles'] as List?) ??
          [];
      final firstSub =
          subs.isNotEmpty ? Map<String, dynamic>.from(subs.first as Map) : null;
      final styleFromSub =
          (firstSub?['style'] as Map?)?.cast<String, dynamic>() ?? {};
      final styleFromEditor =
          (editorMap['caption_style'] as Map?)?.cast<String, dynamic>() ?? {};
      final presetName = editorMap['caption_preset']?.toString() ??
          styleFromSub['preset']?.toString() ??
          'classic';
      setState(() {
        _clipDetail = detail;
        _editorState = editor;
        _captionSync = sync;
        _presets = allPresets;
        _systemPresets = {
          for (final e in system.entries)
            e.key: Map<String, dynamic>.from(e.value as Map),
        };
        _customPresets = {
          for (final e in custom.entries)
            e.key: Map<String, dynamic>.from(e.value as Map),
        };
        _tracks = ((editor['audio_tracks'] as List?) ?? [])
            .map((e) => Map<String, dynamic>.from(e as Map))
            .toList();
        _start = (detail['start_seconds'] as num?)?.toDouble() ?? 0;
        _end = (detail['end_seconds'] as num?)?.toDouble() ?? 15;
        _aspect = detail['aspect_ratio']?.toString() ?? '9:16';
        _zoom = (editorMap['zoom'] as num?)?.toDouble() ?? 1.0;
        _opacity = (editorMap['opacity'] as num?)?.toDouble() ?? 1.0;
        _masterVolume = (editorMap['master_volume'] as num?)?.toDouble() ?? 1.0;
        _captionPreset = presetName;
        _captionStyle = {
          ...Map<String, dynamic>.from(
            (allPresets[presetName] as Map?) ?? const {},
          ),
          ...styleFromSub,
          ...styleFromEditor,
        };
        _voiceTrackId = editorMap['caption_voice_track_id']?.toString() ??
            sync?['caption_voice_track_id']?.toString();
        _subtitleId = firstSub?['id']?.toString();
        _cues = ((firstSub?['content'] as List?) ?? [])
            .map((e) => Map<String, dynamic>.from(e as Map))
            .toList();
        _message = null;
      });
      _syncOffsetControllers();
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

  Map<String, dynamic> _flattenPresets(Map<String, dynamic> payload) {
    if (payload.containsKey('all') && payload['all'] is Map) {
      return {
        for (final e in (payload['all'] as Map).entries)
          e.key.toString(): Map<String, dynamic>.from(e.value as Map),
      };
    }
    // Legacy flat map
    if (!payload.containsKey('system') && !payload.containsKey('custom')) {
      return {
        for (final e in payload.entries)
          if (e.value is Map)
            e.key: Map<String, dynamic>.from(e.value as Map),
      };
    }
    final out = <String, dynamic>{};
    for (final bucket in ['system', 'custom']) {
      final map = payload[bucket];
      if (map is Map) {
        for (final e in map.entries) {
          out[e.key.toString()] = Map<String, dynamic>.from(e.value as Map);
        }
      }
    }
    return out;
  }

  Future<void> _persistCaptionStyle([Map<String, dynamic>? style]) async {
    final next = style ?? _captionStyle;
    setState(() => _captionStyle = Map<String, dynamic>.from(next));
    await _persistEditor({
      'caption_preset': _captionPreset,
      'caption_style': next,
    });
    if (_subtitleId != null) {
      try {
        final updated = await ref.read(apiClientProvider).applyCaptionStyle(
              _subtitleId!,
              style: next,
              preset: _captionPreset,
            );
        setState(() {
          _cues = ((updated['content'] as List?) ?? [])
              .map((e) => Map<String, dynamic>.from(e as Map))
              .toList();
          final s = (updated['style'] as Map?)?.cast<String, dynamic>();
          if (s != null) _captionStyle = {..._captionStyle, ...s};
        });
      } catch (error) {
        setState(() => _message = 'Style apply failed: $error');
      }
    }
  }

  Future<void> _selectPreset(String key) async {
    final base = Map<String, dynamic>.from(
      (_presets[key] as Map?) ?? const {},
    );
    // Keep text corrections / source; replace visual props from preset
    final source = _captionStyle['source'];
    setState(() {
      _captionPreset = key;
      _captionStyle = {
        ...base,
        if (source != null) 'source': source,
        'preset': key,
      };
    });
    await _persistCaptionStyle(_captionStyle);
  }

  Future<void> _saveAsCustomPreset() async {
    final nameController = TextEditingController(
      text: '${_captionStyle['label'] ?? _captionPreset} custom',
    );
    final name = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Save custom preset'),
        content: TextField(
          controller: nameController,
          decoration: const InputDecoration(labelText: 'Preset name'),
          autofocus: true,
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, nameController.text.trim()),
            child: const Text('Save'),
          ),
        ],
      ),
    );
    if (name == null || name.isEmpty) return;
    setState(() => _busy = true);
    try {
      final saved = await ref.read(apiClientProvider).saveCustomCaptionPreset(
            style: _captionStyle,
            name: name,
          );
      final id = saved['id']?.toString() ?? saved['preset']?.toString();
      if (_selectedClipId != null) await _loadClip(_selectedClipId!);
      if (id != null) {
        setState(() {
          _captionPreset = id;
          _captionStyle = {..._captionStyle, ...saved};
          _message = 'Custom preset "$name" saved.';
        });
      }
    } catch (error) {
      setState(() => _message = 'Save preset failed: $error');
    } finally {
      setState(() => _busy = false);
    }
  }

  Future<void> _resetStyleProperty(String key) async {
    final base = Map<String, dynamic>.from(
      (_presets[_captionPreset] as Map?) ??
          (_systemPresets['classic'] as Map?) ??
          const {},
    );
    if (!base.containsKey(key)) {
      final next = Map<String, dynamic>.from(_captionStyle)..remove(key);
      await _persistCaptionStyle(next);
      return;
    }
    await _persistCaptionStyle({..._captionStyle, key: base[key]});
  }

  void _syncOffsetControllers() {
    final ids = _tracks.map((t) => t['id']?.toString() ?? '').toSet();
    for (final id in _offsetControllers.keys.toList()) {
      if (!ids.contains(id)) {
        _offsetControllers.remove(id)?.dispose();
      }
    }
    for (final track in _tracks) {
      final id = track['id']?.toString();
      if (id == null) continue;
      final value = ((track['offset_seconds'] as num?) ??
              (track['start_seconds'] as num?) ??
              0)
          .toDouble();
      final existing = _offsetControllers[id];
      if (existing == null) {
        _offsetControllers[id] =
            TextEditingController(text: value.toStringAsFixed(2));
      } else if (existing.text != value.toStringAsFixed(2)) {
        existing.text = value.toStringAsFixed(2);
      }
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
            sourceTrackId: _voiceTrackId,
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

  Future<void> _previewRegenerate() async {
    if (_selectedClipId == null) return;
    setState(() {
      _busy = true;
      _message = 'Transcribing selected voice track for caption preview…';
    });
    try {
      final draft = await ref.read(apiClientProvider).previewCaptionRegenerate(
            _selectedClipId!,
            sourceTrackId: _voiceTrackId,
          );
      setState(() {
        _captionDraft = draft;
        _message =
            'Draft ready: ${(draft['proposed_cues'] as List?)?.length ?? 0} proposed cues. Review before applying.';
      });
    } catch (error) {
      setState(() => _message = 'Caption preview failed: $error');
    } finally {
      setState(() => _busy = false);
    }
  }

  Future<void> _applyRegenerate({bool keepCorrections = true}) async {
    if (_selectedClipId == null || _captionDraft == null) return;
    setState(() => _busy = true);
    try {
      final result = await ref.read(apiClientProvider).applyCaptionRegenerate(
            _selectedClipId!,
            draftId: _captionDraft!['draft_id']?.toString(),
            keepManualCorrections: keepCorrections,
          );
      setState(() {
        _captionDraft = null;
        _subtitleId = result['id']?.toString();
        _cues = ((result['content'] as List?) ?? [])
            .map((e) => Map<String, dynamic>.from(e as Map))
            .toList();
        _message =
            'Captions regenerated (${_cues.length} cues). Styles preserved.';
      });
      await _loadClip(_selectedClipId!);
    } catch (error) {
      setState(() => _message = 'Apply regenerate failed: $error');
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
            style: _captionStyle.isEmpty ? null : _captionStyle,
          );
      await _persistEditor({
        'caption_preset': _captionPreset,
        'caption_style': _captionStyle,
      });
      setState(() => _message = 'Captions + style saved (ASS regenerated).');
    } catch (error) {
      setState(() => _message = 'Caption save failed: $error');
    } finally {
      setState(() => _busy = false);
    }
  }

  Future<void> _applyTextCorrection() async {
    if (_subtitleId == null || _selectedCueIndex == null) return;
    final find = _correctionFind.trim();
    final replace = _correctionReplace.trim();
    if (find.isEmpty || replace.isEmpty) {
      setState(() => _message = 'Enter the incorrect word and the correction.');
      return;
    }
    setState(() => _busy = true);
    try {
      final updated = await ref.read(apiClientProvider).correctCaptionText(
            _subtitleId!,
            cueIndex: _selectedCueIndex!,
            newText: replace,
            replacePhrase: find,
          );
      setState(() {
        _cues = ((updated['content'] as List?) ?? [])
            .map((e) => Map<String, dynamic>.from(e as Map))
            .toList();
        _message = 'Corrected "$find" → "$replace" (style unchanged).';
        _correctionFind = '';
        _correctionReplace = '';
      });
    } catch (error) {
      setState(() => _message = 'Correction failed: $error');
    } finally {
      setState(() => _busy = false);
    }
  }

  Future<void> _restoreCueText(int index) async {
    if (_subtitleId == null) return;
    setState(() => _busy = true);
    try {
      final updated = await ref.read(apiClientProvider).restoreCaptionText(
            _subtitleId!,
            cueIndex: index,
          );
      setState(() {
        _cues = ((updated['content'] as List?) ?? [])
            .map((e) => Map<String, dynamic>.from(e as Map))
            .toList();
        _message = 'Restored original transcription for cue ${index + 1}.';
      });
    } catch (error) {
      setState(() => _message = 'Restore failed: $error');
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

  Future<void> _importAudio({String kind = 'music'}) async {
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
            kind: kind,
          );
      await _loadClip(_selectedClipId!);
      setState(() {
        _message = kind == 'voiceover' || kind == 'narration'
            ? 'Voice track imported. Captions may be out of date — preview regenerate if needed.'
            : 'Audio track imported ($kind).';
      });
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
                'Multi-track audio, caption sync, style previews, text corrections, and independent opacity.',
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
                              child: Stack(
                                fit: StackFit.expand,
                                children: [
                                  // Background plate (not affected by video opacity)
                                  const ColoredBox(color: Colors.black),
                                  // VIDEO LAYER ONLY — captions are a sibling above
                                  Opacity(
                                    opacity: _opacity.clamp(0.0, 1.0),
                                    child: LocalVideoPreview(
                                      key: ValueKey(filePath ?? browserUrl),
                                      filePath: filePath,
                                      networkUrl: browserUrl,
                                    ),
                                  ),
                                  // CAPTIONS LAYER — independent opacity / styles
                                  if (_cues.isNotEmpty)
                                    CaptionOverlayLayer(
                                      text: (_selectedCueIndex != null
                                              ? _cues[_selectedCueIndex!]
                                              : _cues.first)['text']
                                          ?.toString() ??
                                          '',
                                      style: _captionStyle.isNotEmpty
                                          ? _captionStyle
                                          : {
                                              'font_name': 'Arial',
                                              'font_size': 48,
                                              'primary_colour': '&H00FFFFFF',
                                              'text_opacity': 1.0,
                                              'alignment': 2,
                                              'margin_v': 80,
                                            },
                                      selected: _captionSelected,
                                      onSelect: () => setState(() {
                                        _captionSelected = true;
                                        _tabs.index = 2;
                                      }),
                                      onStyleChanged: (next) {
                                        setState(() => _captionStyle = next);
                                      },
                                    ),
                                ],
                              ),
                            ),
                            if (_cues.isNotEmpty)
                              Padding(
                                padding: const EdgeInsets.fromLTRB(12, 4, 12, 0),
                                child: Row(
                                  children: [
                                    const Text(
                                      'Drag caption on preview to reposition',
                                      style: TextStyle(
                                        color: AppTheme.textSecondary,
                                        fontSize: 11,
                                      ),
                                    ),
                                    const Spacer(),
                                    TextButton(
                                      onPressed: _busy
                                          ? null
                                          : () => _persistCaptionStyle(),
                                      child: const Text('Save caption position'),
                                    ),
                                  ],
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
              'offset ${((track['offset_seconds'] as num?) ?? (track['start_seconds'] as num?) ?? 0).toStringAsFixed(1)}s',
              style: const TextStyle(color: AppTheme.textSecondary),
            ),
          ),
      ],
    );
  }

  Widget _buildAudioTab() {
    final staleVoice = _captionSync?['captions_stale'] == true;
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
        if (staleVoice)
          Container(
            margin: const EdgeInsets.only(bottom: 10),
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: AppTheme.warning.withOpacity(0.12),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: AppTheme.warning.withOpacity(0.5)),
            ),
            child: const Text(
              'Voice track used for captions may have changed. Open Captions → Preview regenerate.',
              style: TextStyle(color: AppTheme.warning),
            ),
          ),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            OutlinedButton.icon(
              onPressed: _busy ? null : () => _importAudio(kind: 'music'),
              icon: const Icon(Icons.library_music),
              label: const Text('Import music'),
            ),
            OutlinedButton.icon(
              onPressed: _busy ? null : () => _importAudio(kind: 'voiceover'),
              icon: const Icon(Icons.record_voice_over),
              label: const Text('Import voice-over'),
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
          Builder(
            builder: (context) {
              final id = track['id'] as String;
              final offset = ((track['offset_seconds'] as num?) ??
                      (track['start_seconds'] as num?) ??
                      0)
                  .toDouble();
              final controller = _offsetControllers[id] ??
                  TextEditingController(text: offset.toStringAsFixed(2));
              _offsetControllers[id] = controller;
              final isVoice = const {
                'original',
                'voiceover',
                'stem_vocals',
                'narration',
                'external',
              }.contains(track['kind']);
              return Container(
                margin: const EdgeInsets.only(bottom: 10),
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AppTheme.surface,
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(
                    color: _voiceTrackId == id
                        ? AppTheme.accent
                        : AppTheme.border,
                  ),
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
                        if (isVoice)
                          TextButton(
                            onPressed: _busy
                                ? null
                                : () async {
                                    setState(() => _voiceTrackId = id);
                                    await ref
                                        .read(apiClientProvider)
                                        .setCaptionVoiceTrack(
                                          _selectedClipId!,
                                          trackId: id,
                                        );
                                    await _persistEditor(
                                      {'caption_voice_track_id': id},
                                    );
                                    setState(
                                      () => _message =
                                          'Caption voice source → ${track['name']}',
                                    );
                                  },
                            child: Text(
                              _voiceTrackId == id
                                  ? 'Caption source'
                                  : 'Use for captions',
                            ),
                          ),
                        Switch(
                          value: track['enabled'] != false,
                          onChanged: (v) => _updateTrack(id, {'enabled': v}),
                        ),
                      ],
                    ),
                    Wrap(
                      spacing: 8,
                      children: [
                        FilterChip(
                          label: Text(
                            track['muted'] == true ? 'Muted' : 'Audible',
                          ),
                          selected: track['muted'] == true,
                          onSelected: (v) => _updateTrack(id, {'muted': v}),
                        ),
                        FilterChip(
                          label: Text(
                            track['exclude_from_export'] == true
                                ? 'Exclude export'
                                : 'In export',
                          ),
                          selected: track['exclude_from_export'] == true,
                          onSelected: (v) =>
                              _updateTrack(id, {'exclude_from_export': v}),
                        ),
                      ],
                    ),
                    Text(
                      'Volume ${(((track['volume'] as num?)?.toDouble() ?? 1) * 100).round()}%',
                    ),
                    Slider(
                      value: ((track['volume'] as num?)?.toDouble() ?? 1)
                          .clamp(0, 2),
                      min: 0,
                      max: 2,
                      onChangeEnd: (v) => _updateTrack(id, {'volume': v}),
                      onChanged: (_) {},
                    ),
                    Text(
                      'Offset ${offset.toStringAsFixed(2)}s  · starts at ${offset.toStringAsFixed(2)}s on the clip timeline',
                    ),
                    Row(
                      children: [
                        Expanded(
                          child: Slider(
                            value: offset.clamp(0, 120),
                            min: 0,
                            max: 120,
                            onChanged: (v) {
                              controller.text = v.toStringAsFixed(2);
                              setState(() {
                                track['start_seconds'] = v;
                                track['offset_seconds'] = v;
                              });
                            },
                            onChangeEnd: (v) =>
                                _updateTrack(id, {'offset_seconds': v}),
                          ),
                        ),
                        SizedBox(
                          width: 72,
                          child: TextField(
                            controller: controller,
                            keyboardType: const TextInputType.numberWithOptions(
                              decimal: true,
                            ),
                            decoration: const InputDecoration(
                              isDense: true,
                              labelText: 'sec',
                            ),
                            onSubmitted: (raw) {
                              final v = double.tryParse(raw.replaceAll(',', '.'));
                              if (v == null || v < 0) return;
                              _updateTrack(id, {'offset_seconds': v});
                            },
                          ),
                        ),
                        TextButton(
                          onPressed: () {
                            controller.text = '0.00';
                            _updateTrack(id, {'offset_seconds': 0.0});
                          },
                          child: const Text('Reset'),
                        ),
                      ],
                    ),
                    if (track['kind'] != 'original')
                      Align(
                        alignment: Alignment.centerRight,
                        child: TextButton(
                          onPressed: () async {
                            await ref
                                .read(apiClientProvider)
                                .deleteAudioTrack(id);
                            if (_selectedClipId != null) {
                              await _loadClip(_selectedClipId!);
                            }
                          },
                          child: const Text('Delete'),
                        ),
                      ),
                  ],
                ),
              );
            },
          ),
      ],
    );
  }

  Widget _buildCaptionsTab() {
    final stale = _captionSync?['captions_stale'] == true;
    final voiceTracks = (_captionSync?['voice_tracks'] as List?)
            ?.map((e) => Map<String, dynamic>.from(e as Map))
            .toList() ??
        _tracks
            .where(
              (t) => const {
                'original',
                'voiceover',
                'stem_vocals',
                'narration',
                'external',
              }.contains(t['kind']),
            )
            .toList();
    final systemEntries = _systemPresets.isNotEmpty
        ? _systemPresets.entries.toList()
        : _presets.entries
            .where((e) => (e.value as Map)['system'] != false)
            .toList();
    final customEntries = _customPresets.entries.toList();

    return ListView(
      padding: const EdgeInsets.only(top: 12),
      children: [
        if (stale)
          Container(
            margin: const EdgeInsets.only(bottom: 10),
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: AppTheme.warning.withOpacity(0.12),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: AppTheme.warning.withOpacity(0.5)),
            ),
            child: const Text(
              'Transcription may be out of date for the current voice source. '
              'Preview a new transcription before applying — manual corrections are kept unless you opt out.',
              style: TextStyle(color: AppTheme.warning),
            ),
          ),
        DropdownButtonFormField<String>(
          value: voiceTracks.any((t) => t['id'] == _voiceTrackId)
              ? _voiceTrackId
              : null,
          decoration: const InputDecoration(
            labelText: 'Voice track for captions',
            helperText: 'Music/sfx never trigger caption regeneration',
          ),
          items: [
            for (final t in voiceTracks)
              DropdownMenuItem(
                value: t['id']?.toString(),
                child: Text('${t['name']} (${t['kind']})'),
              ),
          ],
          onChanged: (id) async {
            setState(() => _voiceTrackId = id);
            if (_selectedClipId != null) {
              await ref
                  .read(apiClientProvider)
                  .setCaptionVoiceTrack(_selectedClipId!, trackId: id);
              await _loadClip(_selectedClipId!);
            }
          },
        ),
        const SizedBox(height: 12),
        Text(
          'System presets (starting points — fully editable after select)',
          style: Theme.of(context).textTheme.titleSmall,
        ),
        const SizedBox(height: 8),
        SizedBox(
          height: 110,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            itemCount: systemEntries.length,
            separatorBuilder: (_, __) => const SizedBox(width: 8),
            itemBuilder: (context, index) {
              final entry = systemEntries[index];
              final style = Map<String, dynamic>.from(entry.value as Map);
              return SizedBox(
                width: 180,
                child: CaptionStylePreview(
                  style: style,
                  label: style['label']?.toString() ?? entry.key,
                  selected: _captionPreset == entry.key,
                  onTap: () => _selectPreset(entry.key),
                ),
              );
            },
          ),
        ),
        if (customEntries.isNotEmpty) ...[
          const SizedBox(height: 10),
          Text(
            'Custom presets',
            style: Theme.of(context).textTheme.titleSmall,
          ),
          const SizedBox(height: 8),
          SizedBox(
            height: 110,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              itemCount: customEntries.length,
              separatorBuilder: (_, __) => const SizedBox(width: 8),
              itemBuilder: (context, index) {
                final entry = customEntries[index];
                final style = Map<String, dynamic>.from(entry.value as Map);
                return SizedBox(
                  width: 180,
                  child: CaptionStylePreview(
                    style: style,
                    label: style['label']?.toString() ?? entry.key,
                    selected: _captionPreset == entry.key,
                    onTap: () => _selectPreset(entry.key),
                  ),
                );
              },
            ),
          ),
        ],
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            FilledButton.tonal(
              onPressed: _busy ? null : _saveAsCustomPreset,
              child: const Text('Save as custom preset'),
            ),
            OutlinedButton(
              onPressed: _busy
                  ? null
                  : () async {
                      final dup = await ref
                          .read(apiClientProvider)
                          .duplicateCaptionPreset(_captionPreset);
                      if (_selectedClipId != null) {
                        await _loadClip(_selectedClipId!);
                      }
                      setState(
                        () => _message =
                            'Duplicated preset → ${dup['label'] ?? dup['id']}',
                      );
                    },
              child: const Text('Duplicate preset'),
            ),
            if (_customPresets.containsKey(_captionPreset))
              TextButton(
                onPressed: _busy
                    ? null
                    : () async {
                        await ref
                            .read(apiClientProvider)
                            .deleteCustomCaptionPreset(_captionPreset);
                        await _selectPreset('classic');
                        if (_selectedClipId != null) {
                          await _loadClip(_selectedClipId!);
                        }
                      },
                child: const Text('Delete custom'),
              ),
            if (_systemPresets.containsKey(_captionPreset))
              TextButton(
                onPressed: _busy
                    ? null
                    : () async {
                        final restored = await ref
                            .read(apiClientProvider)
                            .restoreSystemCaptionPreset(_captionPreset);
                        setState(() {
                          _captionStyle = {
                            ..._captionStyle,
                            ...restored,
                            'preset': _captionPreset,
                          };
                        });
                        await _persistCaptionStyle(_captionStyle);
                        setState(
                          () => _message =
                              'Restored system defaults for $_captionPreset',
                        );
                      },
                child: const Text('Restore system defaults'),
              ),
          ],
        ),
        const SizedBox(height: 8),
        CaptionStyleEditor(
          style: _captionStyle.isNotEmpty
              ? _captionStyle
              : {
                  'font_name': 'Arial',
                  'font_size': 48,
                  'primary_colour': '&H00FFFFFF',
                  'text_opacity': 1.0,
                },
          onChanged: (next) {
            setState(() => _captionStyle = next);
          },
          onResetProperty: _resetStyleProperty,
        ),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            FilledButton(
              onPressed: _busy ? null : () => _persistCaptionStyle(),
              child: const Text('Apply style'),
            ),
            OutlinedButton(
              onPressed: _busy ? null : () => _generateCaptions(),
              child: const Text('Generate / keep edits'),
            ),
            OutlinedButton(
              onPressed: _busy ? null : _previewRegenerate,
              child: const Text('Preview from voice track'),
            ),
            OutlinedButton(
              onPressed: _busy ? null : () => _generateCaptions(replace: true),
              child: const Text('Replace from media transcript'),
            ),
            FilledButton.tonal(
              onPressed: _busy ? null : _saveCaptions,
              child: const Text('Save captions'),
            ),
          ],
        ),
        if (_captionDraft != null) ...[
          const SizedBox(height: 12),
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: AppTheme.surfaceAlt,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: AppTheme.border),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Compare transcription',
                  style: Theme.of(context).textTheme.titleSmall,
                ),
                const SizedBox(height: 6),
                Text(
                  'Current: ${(_captionDraft!['comparison'] as Map?)?['current_count'] ?? 0} cues · '
                  'Proposed: ${(_captionDraft!['comparison'] as Map?)?['proposed_count'] ?? 0} cues · '
                  'Manual corrections in current: ${_captionDraft!['manual_corrections_in_current'] ?? 0}',
                  style: const TextStyle(color: AppTheme.textSecondary, fontSize: 12),
                ),
                const SizedBox(height: 8),
                Text(
                  'Proposed sample: ${((_captionDraft!['comparison'] as Map?)?['proposed_sample'] as List?)?.take(3).join(' | ') ?? ''}',
                  style: const TextStyle(fontSize: 12),
                ),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 8,
                  children: [
                    FilledButton(
                      onPressed: _busy
                          ? null
                          : () => _applyRegenerate(keepCorrections: true),
                      child: const Text('Apply · keep corrections'),
                    ),
                    OutlinedButton(
                      onPressed: _busy
                          ? null
                          : () => _applyRegenerate(keepCorrections: false),
                      child: const Text('Apply · full replace'),
                    ),
                    TextButton(
                      onPressed: () => setState(() => _captionDraft = null),
                      child: const Text('Keep current captions'),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
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
                color:
                    _selectedCueIndex == i ? AppTheme.accent : AppTheme.border,
              ),
            ),
            child: ListTile(
              dense: true,
              title: TextFormField(
                initialValue: _cues[i]['text']?.toString() ?? '',
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
                '${_cues[i]['manually_corrected'] == true ? ' · corrected' : ''}',
                style: const TextStyle(
                  color: AppTheme.textSecondary,
                  fontSize: 11,
                ),
              ),
              trailing: _cues[i]['manually_corrected'] == true
                  ? IconButton(
                      tooltip: 'Restore original text',
                      onPressed: _busy ? null : () => _restoreCueText(i),
                      icon: const Icon(Icons.undo, size: 18),
                    )
                  : null,
              onTap: () => setState(() => _selectedCueIndex = i),
            ),
          ),
        if (_selectedCueIndex != null) ...[
          const SizedBox(height: 8),
          Text(
            'Text correction (spelling / ASR errors)',
            style: Theme.of(context).textTheme.titleSmall,
          ),
          const Text(
            'Does not change caption style. Timestamps and visuals are preserved.',
            style: TextStyle(color: AppTheme.textSecondary, fontSize: 12),
          ),
          const SizedBox(height: 6),
          Row(
            children: [
              Expanded(
                child: TextFormField(
                  initialValue: _correctionFind,
                  decoration: const InputDecoration(
                    labelText: 'Incorrect word/phrase',
                    isDense: true,
                  ),
                  onChanged: (v) => _correctionFind = v,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: TextFormField(
                  initialValue: _correctionReplace,
                  decoration: const InputDecoration(
                    labelText: 'Correction',
                    isDense: true,
                  ),
                  onChanged: (v) => _correctionReplace = v,
                ),
              ),
              const SizedBox(width: 8),
              FilledButton(
                onPressed: _busy ? null : _applyTextCorrection,
                child: const Text('Correct'),
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
          'Applies only to the video layer. Captions keep their own text/background opacity.',
          style: TextStyle(color: AppTheme.textSecondary),
        ),
        Slider(
          value: _opacity,
          min: 0,
          max: 1,
          onChanged: (v) => setState(() => _opacity = v),
          onChangeEnd: (v) => _persistEditor({'opacity': v}),
        ),
        Text(
          'Preview uses Opacity on LocalVideoPreview only; captions are a sibling Stack layer. '
          'Export burns ASS after video opacity on black.',
          style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: AppTheme.textSecondary,
              ),
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
