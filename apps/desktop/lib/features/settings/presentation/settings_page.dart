import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/services/backend_connection.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets/section_header.dart';

class SettingsPage extends ConsumerWidget {
  const SettingsPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final backend = ref.watch(backendConnectionProvider);
    final system = ref.watch(systemInfoProvider);
    final runtime = ref.watch(runtimeSettingsProvider);

    return Padding(
      padding: const EdgeInsets.all(28),
      child: ListView(
        children: [
          const SectionHeader(
            title: 'Settings',
            subtitle: 'Local runtime configuration and hardware detection.',
          ),
          const SizedBox(height: 24),
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
                  'Max concurrent jobs': '${data['max_concurrent_jobs']}',
                  'Max GPU inference jobs': '${data['max_gpu_inference_jobs']}',
                },
              ),
              loading: () => const LinearProgressIndicator(),
              error: (e, _) => Text('$e', style: const TextStyle(color: AppTheme.danger)),
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
                        'CPU count': '${data['cpu_count']}',
                        'RAM':
                            '${data['ram_available_mb']}/${data['ram_total_mb']} MB available',
                      },
                    ),
                    const SizedBox(height: 16),
                    _SettingsPanel(
                      title: 'FFmpeg',
                      rows: {
                        'Available': '${ffmpeg['available']}',
                        'Path': '${ffmpeg['path'] ?? 'n/a'}',
                        'Version': '${ffmpeg['version'] ?? 'n/a'}',
                        'NVENC': '${ffmpeg['has_nvenc']}',
                        'NVDEC': '${ffmpeg['has_nvdec']}',
                      },
                    ),
                    const SizedBox(height: 16),
                    _SettingsPanel(
                      title: 'GPU / CUDA',
                      rows: {
                        'Available': '${gpu['available']}',
                        'Vendor': '${gpu['vendor'] ?? 'n/a'}',
                        'Name': '${gpu['name'] ?? 'n/a'}',
                        'Driver': '${gpu['driver_version'] ?? 'n/a'}',
                        'CUDA': '${gpu['cuda_available']}',
                        'Note': '${gpu['error'] ?? 'Ready'}',
                      },
                    ),
                  ],
                );
              },
              loading: () => const LinearProgressIndicator(),
              error: (e, _) => Text('$e', style: const TextStyle(color: AppTheme.danger)),
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
