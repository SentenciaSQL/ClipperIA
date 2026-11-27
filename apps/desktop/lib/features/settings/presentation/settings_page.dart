import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/services/backend_connection.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets/section_header.dart';

final aiProviderStatusProvider = FutureProvider<Map<String, dynamic>>((ref) async {
  final status = ref.watch(backendConnectionProvider);
  if (status.state != BackendConnectionState.connected) {
    throw StateError('Backend not connected');
  }
  return ref.watch(apiClientProvider).getAiProviderStatus();
});

final profilesProvider = FutureProvider<Map<String, dynamic>>((ref) async {
  final status = ref.watch(backendConnectionProvider);
  if (status.state != BackendConnectionState.connected) {
    throw StateError('Backend not connected');
  }
  return ref.watch(apiClientProvider).listProfiles();
});

final modelsProvider = FutureProvider<Map<String, dynamic>>((ref) async {
  final status = ref.watch(backendConnectionProvider);
  if (status.state != BackendConnectionState.connected) {
    throw StateError('Backend not connected');
  }
  return ref.watch(apiClientProvider).getModelsInventory();
});

final storageUsageProvider = FutureProvider<Map<String, dynamic>>((ref) async {
  final status = ref.watch(backendConnectionProvider);
  if (status.state != BackendConnectionState.connected) {
    throw StateError('Backend not connected');
  }
  return ref.watch(apiClientProvider).getStorageUsage();
});

final resourcesProvider = FutureProvider<Map<String, dynamic>>((ref) async {
  final status = ref.watch(backendConnectionProvider);
  if (status.state != BackendConnectionState.connected) {
    throw StateError('Backend not connected');
  }
  return ref.watch(apiClientProvider).getSystemResources();
});

class SettingsPage extends ConsumerStatefulWidget {
  const SettingsPage({super.key});

  @override
  ConsumerState<SettingsPage> createState() => _SettingsPageState();
}

class _SettingsPageState extends ConsumerState<SettingsPage> {
  String? _message;
  bool _busy = false;

  Future<void> _setProvider(String mode) async {
    setState(() {
      _busy = true;
      _message = 'Switching AI mode to $mode…';
    });
    try {
      await ref.read(apiClientProvider).setAiProviderMode(mode);
      ref.invalidate(aiProviderStatusProvider);
      ref.invalidate(runtimeSettingsProvider);
      setState(() => _message = 'AI provider mode: $mode');
    } catch (error) {
      setState(() => _message = 'Failed: $error');
    } finally {
      setState(() => _busy = false);
    }
  }

  Future<void> _setProfile(String id) async {
    setState(() => _busy = true);
    try {
      await ref.read(apiClientProvider).setActiveProfile(id);
      ref.invalidate(profilesProvider);
      setState(() => _message = 'Active profile: $id');
    } catch (error) {
      setState(() => _message = 'Profile failed: $error');
    } finally {
      setState(() => _busy = false);
    }
  }

  Future<void> _ensureWhisper(String size) async {
    setState(() {
      _busy = true;
      _message = 'Ensuring Whisper $size (may download)…';
    });
    try {
      await ref.read(apiClientProvider).ensureWhisperModel(modelSize: size);
      ref.invalidate(modelsProvider);
      setState(() => _message = 'Whisper $size ready.');
    } catch (error) {
      setState(() => _message = 'Model ensure failed: $error');
    } finally {
      setState(() => _busy = false);
    }
  }

  Future<void> _cleanupStorage() async {
    setState(() => _busy = true);
    try {
      final result = await ref.read(apiClientProvider).cleanupStorage();
      ref.invalidate(storageUsageProvider);
      setState(
        () => _message =
            'Cleanup freed ${result['freed_mb']} MB (${result['deleted_files']} files).',
      );
    } catch (error) {
      setState(() => _message = 'Cleanup failed: $error');
    } finally {
      setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final backend = ref.watch(backendConnectionProvider);
    final system = ref.watch(systemInfoProvider);
    final runtime = ref.watch(runtimeSettingsProvider);
    final providers = ref.watch(aiProviderStatusProvider);
    final profiles = ref.watch(profilesProvider);
    final models = ref.watch(modelsProvider);
    final storage = ref.watch(storageUsageProvider);
    final resources = ref.watch(resourcesProvider);

    return Padding(
      padding: const EdgeInsets.all(28),
      child: ListView(
        children: [
          const SectionHeader(
            title: 'Settings',
            subtitle:
                'Hybrid AI providers, processing profiles, models, and storage.',
          ),
          const SizedBox(height: 16),
          if (_message != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Text(
                _message!,
                style: const TextStyle(color: AppTheme.textSecondary),
              ),
            ),
          if (_busy) const LinearProgressIndicator(),
          if (backend.state != BackendConnectionState.connected)
            Text(
              'Connect to the backend to load system settings.',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: AppTheme.textSecondary,
                  ),
            )
          else ...[
            runtime.when(
              data: (data) => _SettingsPanel(
                title: 'Runtime',
                rows: {
                  'App': '${data['app_name']} v${data['app_version']}',
                  'Environment': '${data['environment']}',
                  'API': 'http://${data['host']}:${data['port']}',
                  'Data root': '${data['data_root']}',
                  'AI provider': '${data['ai_provider']}',
                  'Cloud LLM': data['cloud_llm_configured'] == true
                      ? '${data['cloud_llm_model']} @ ${data['cloud_llm_base_url']}'
                      : 'not configured',
                  'Max concurrent jobs': '${data['max_concurrent_jobs']}',
                  'Max GPU inference jobs': '${data['max_gpu_inference_jobs']}',
                },
              ),
              loading: () => const LinearProgressIndicator(),
              error: (e, _) =>
                  Text('$e', style: const TextStyle(color: AppTheme.danger)),
            ),
            const SizedBox(height: 16),
            providers.when(
              data: (data) {
                final local =
                    (data['local'] as Map?)?.cast<String, dynamic>() ?? {};
                final cloud =
                    (data['cloud'] as Map?)?.cast<String, dynamic>() ?? {};
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _SettingsPanel(
                      title: 'AI providers',
                      rows: {
                        'Default mode': '${data['default_mode']}',
                        'Local Ollama':
                            '${local['available'] == true ? 'online' : 'offline'} · ${local['model']}',
                        'Cloud LLM':
                            '${cloud['available'] == true ? 'ready' : 'no API key'} · ${cloud['model']}',
                      },
                    ),
                    const SizedBox(height: 8),
                    Wrap(
                      spacing: 8,
                      children: [
                        for (final mode in ['local', 'auto', 'cloud'])
                          OutlinedButton(
                            onPressed: _busy ? null : () => _setProvider(mode),
                            child: Text(mode),
                          ),
                      ],
                    ),
                  ],
                );
              },
              loading: () => const LinearProgressIndicator(),
              error: (e, _) => Text('$e'),
            ),
            const SizedBox(height: 16),
            profiles.when(
              data: (data) {
                final active = data['active']?.toString() ?? 'balanced';
                final map =
                    (data['profiles'] as Map?)?.cast<String, dynamic>() ?? {};
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Processing profiles (active: $active)',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 8),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: [
                        for (final entry in map.entries)
                          ChoiceChip(
                            label: Text(
                              (entry.value is Map
                                      ? (entry.value as Map)['label']
                                      : entry.key)
                                  ?.toString() ??
                                  entry.key,
                            ),
                            selected: entry.key == active,
                            onSelected: _busy
                                ? null
                                : (_) => _setProfile(entry.key),
                          ),
                      ],
                    ),
                  ],
                );
              },
              loading: () => const LinearProgressIndicator(),
              error: (e, _) => Text('$e'),
            ),
            const SizedBox(height: 16),
            models.when(
              data: (data) {
                final whisper =
                    (data['whisper'] as Map?)?.cast<String, dynamic>() ?? {};
                final installed = (whisper['installed'] as List?) ?? [];
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _SettingsPanel(
                      title: 'Model management',
                      rows: {
                        'Models dir': '${data['models_dir']}',
                        'Default Whisper': '${whisper['default_size']}',
                        'Installed': installed.isEmpty
                            ? 'none yet'
                            : installed
                                .map((e) => (e as Map)['name'])
                                .join(', '),
                      },
                    ),
                    const SizedBox(height: 8),
                    Wrap(
                      spacing: 8,
                      children: [
                        for (final size in ['tiny', 'base', 'small'])
                          OutlinedButton(
                            onPressed:
                                _busy ? null : () => _ensureWhisper(size),
                            child: Text('Ensure $size'),
                          ),
                      ],
                    ),
                  ],
                );
              },
              loading: () => const LinearProgressIndicator(),
              error: (e, _) => Text('$e'),
            ),
            const SizedBox(height: 16),
            storage.when(
              data: (data) => Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _SettingsPanel(
                    title: 'Storage',
                    rows: {
                      'Data root': '${data['data_root']}',
                      'Used': '${data['total_used_mb']} MB',
                      'Disk free': '${data['disk_free_mb']} MB',
                      'Cache max': '${data['cache_max_mb']} MB',
                    },
                  ),
                  const SizedBox(height: 8),
                  OutlinedButton.icon(
                    onPressed: _busy ? null : _cleanupStorage,
                    icon: const Icon(Icons.cleaning_services_outlined),
                    label: const Text('Cleanup cache'),
                  ),
                ],
              ),
              loading: () => const LinearProgressIndicator(),
              error: (e, _) => Text('$e'),
            ),
            const SizedBox(height: 16),
            resources.when(
              data: (data) {
                final host =
                    (data['host'] as Map?)?.cast<String, dynamic>() ?? {};
                final recs = (data['recommendations'] as List?) ?? [];
                return _SettingsPanel(
                  title: 'Resources',
                  rows: {
                    'CPU': '${host['cpu_count']}',
                    'RAM available': '${host['ram_available_mb']} MB',
                    'RAM used': '${host['ram_used_pct']}%',
                    'Tips': recs.isEmpty
                        ? 'System looks healthy'
                        : recs.join(' · '),
                  },
                );
              },
              loading: () => const LinearProgressIndicator(),
              error: (e, _) => Text('$e'),
            ),
            const SizedBox(height: 16),
            system.when(
              data: (data) {
                final ffmpeg =
                    (data['ffmpeg'] as Map?)?.cast<String, dynamic>() ?? {};
                final gpu =
                    (data['gpu'] as Map?)?.cast<String, dynamic>() ?? {};
                return Column(
                  children: [
                    _SettingsPanel(
                      title: 'Host',
                      rows: {
                        'Platform':
                            '${data['platform']} ${data['platform_release']}',
                        'Architecture': '${data['architecture']}',
                        'Python': '${data['python_version']}',
                      },
                    ),
                    const SizedBox(height: 16),
                    _SettingsPanel(
                      title: 'FFmpeg',
                      rows: {
                        'Available': '${ffmpeg['available']}',
                        'NVENC': '${ffmpeg['has_nvenc']}',
                        'NVDEC': '${ffmpeg['has_nvdec']}',
                      },
                    ),
                    const SizedBox(height: 16),
                    _SettingsPanel(
                      title: 'GPU / CUDA',
                      rows: {
                        'Available': '${gpu['available']}',
                        'Name': '${gpu['name'] ?? 'n/a'}',
                        'CUDA': '${gpu['cuda_available']}',
                      },
                    ),
                  ],
                );
              },
              loading: () => const LinearProgressIndicator(),
              error: (e, _) =>
                  Text('$e', style: const TextStyle(color: AppTheme.danger)),
            ),
          ],
        ],
      ),
    );
  }
}

class _SettingsPanel extends StatelessWidget {
  const _SettingsPanel({required this.title, required this.rows});

  final String title;
  final Map<String, String> rows;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: AppTheme.surfaceAlt,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w600,
                ),
          ),
          const SizedBox(height: 12),
          for (final entry in rows.entries)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  SizedBox(
                    width: 180,
                    child: Text(
                      entry.key,
                      style: const TextStyle(color: AppTheme.textSecondary),
                    ),
                  ),
                  Expanded(child: Text(entry.value)),
                ],
              ),
            ),
        ],
      ),
    );
  }
}
