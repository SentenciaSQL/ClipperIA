import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/services/backend_connection.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets/section_header.dart';
import '../../../shared/widgets/stat_tile.dart';

class DashboardPage extends ConsumerWidget {
  const DashboardPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final backend = ref.watch(backendConnectionProvider);
    final overview = ref.watch(dashboardOverviewProvider);
    final events = ref.watch(websocketEventsProvider);

    return Padding(
      padding: const EdgeInsets.all(28),
      child: ListView(
        children: [
          const SectionHeader(
            title: 'Dashboard',
            subtitle: 'Local processing overview and system readiness.',
          ),
          const SizedBox(height: 24),
          if (backend.state != BackendConnectionState.connected)
            _ConnectionBanner(backend: backend)
          else
            overview.when(
              data: (data) => _DashboardBody(data: data, events: events),
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (error, _) => Text(
                'Failed to load dashboard: $error',
                style: const TextStyle(color: AppTheme.danger),
              ),
            ),
        ],
      ),
    );
  }
}

class _ConnectionBanner extends ConsumerWidget {
  const _ConnectionBanner({required this.backend});

  final BackendStatus backend;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppTheme.surfaceAlt,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Backend not connected',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 8),
          Text(
            backend.message ??
                'Start the local FastAPI backend, then reconnect.',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: AppTheme.textSecondary,
                ),
          ),
          const SizedBox(height: 16),
          FilledButton.icon(
            onPressed: () =>
                ref.read(backendConnectionProvider.notifier).connect(),
            icon: const Icon(Icons.link),
            label: const Text('Connect'),
          ),
        ],
      ),
    );
  }
}

class _DashboardBody extends StatelessWidget {
  const _DashboardBody({required this.data, required this.events});

  final Map<String, dynamic> data;
  final AsyncValue<Map<String, dynamic>> events;

  @override
  Widget build(BuildContext context) {
    final gpu = (data['gpu'] as Map?)?.cast<String, dynamic>() ?? {};
    final stats =
        (data['processing_statistics'] as Map?)?.cast<String, dynamic>() ?? {};
    final projects =
        (data['recent_projects'] as List?)?.cast<Map<String, dynamic>>() ?? [];
    final streams =
        (data['active_streams'] as List?)?.cast<Map<String, dynamic>>() ?? [];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        LayoutBuilder(
          builder: (context, constraints) {
            final width = constraints.maxWidth;
            final crossAxisCount = width > 1100
                ? 4
                : width > 800
                    ? 3
                    : 2;
            return GridView.count(
              crossAxisCount: crossAxisCount,
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              mainAxisSpacing: 14,
              crossAxisSpacing: 14,
              childAspectRatio: 1.55,
              children: [
                StatTile(
                  label: 'Imported videos',
                  value: '${data['total_imported_videos'] ?? 0}',
                  icon: Icons.video_file_outlined,
                ),
                StatTile(
                  label: 'Generated clips',
                  value: '${data['total_generated_clips'] ?? 0}',
                  icon: Icons.movie_creation_outlined,
                ),
                StatTile(
                  label: 'Active jobs',
                  value: '${data['active_processing_jobs'] ?? 0}',
                  icon: Icons.hourglass_top_outlined,
                ),
                StatTile(
                  label: 'Completed jobs',
                  value: '${data['completed_jobs'] ?? 0}',
                  icon: Icons.check_circle_outline,
                ),
              ],
            );
          },
        ),
        const SizedBox(height: 24),
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: _InfoPanel(
                title: 'GPU',
                children: [
                  _kv('Available', '${gpu['available'] == true}'),
                  _kv('Name', '${gpu['name'] ?? 'Not detected'}'),
                  _kv(
                    'Utilization',
                    gpu['utilization_percent'] == null
                        ? 'n/a'
                        : '${gpu['utilization_percent']}%',
                  ),
                  _kv(
                    'VRAM',
                    gpu['vram_total_mb'] == null
                        ? 'n/a'
                        : '${gpu['vram_used_mb']}/${gpu['vram_total_mb']} MB',
                  ),
                ],
              ),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: _InfoPanel(
                title: 'Processing',
                children: [
                  _kv('CPU cores', '${stats['cpu_count'] ?? '-'}'),
                  _kv(
                    'RAM',
                    stats['ram_total_mb'] == null
                        ? 'n/a'
                        : '${stats['ram_available_mb']}/${stats['ram_total_mb']} MB free',
                  ),
                  _kv('FFmpeg', '${stats['ffmpeg_available'] == true}'),
                  _kv(
                    'WebSocket event',
                    events.maybeWhen(
                      data: (e) => '${e['type']}',
                      orElse: () => 'waiting…',
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
        const SizedBox(height: 24),
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: _InfoPanel(
                title: 'Recent projects',
                children: projects.isEmpty
                    ? [
                        Text(
                          'No projects yet. Import begins in Phase 2.',
                          style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                                color: AppTheme.textSecondary,
                              ),
                        ),
                      ]
                    : [
                        for (final project in projects)
                          _kv(
                            '${project['name']}',
                            '${project['status']}',
                          ),
                      ],
              ),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: _InfoPanel(
                title: 'Active streams',
                children: streams.isEmpty
                    ? [
                        Text(
                          'No live sessions. Live monitor arrives in Phase 7.',
                          style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                                color: AppTheme.textSecondary,
                              ),
                        ),
                      ]
                    : [
                        for (final stream in streams)
                          _kv(
                            '${stream['title'] ?? stream['id']}',
                            '${stream['status']}',
                          ),
                      ],
              ),
            ),
          ],
        ),
      ],
    );
  }

  static Widget _kv(String key, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        children: [
          Expanded(
            child: Text(
              key,
              style: const TextStyle(color: AppTheme.textSecondary),
            ),
          ),
          Text(value),
        ],
      ),
    );
  }
}

class _InfoPanel extends StatelessWidget {
  const _InfoPanel({required this.title, required this.children});

  final String title;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return Container(
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
          ...children,
        ],
      ),
    );
  }
}
