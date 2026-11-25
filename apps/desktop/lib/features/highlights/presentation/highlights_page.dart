import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/services/backend_connection.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets/section_header.dart';
import '../../video_library/presentation/video_library_providers.dart';

final highlightsProvider = FutureProvider<List<Map<String, dynamic>>>((ref) async {
  final status = ref.watch(backendConnectionProvider);
  if (status.state != BackendConnectionState.connected) return [];
  return ref.watch(apiClientProvider).listHighlights();
});

final jobsProvider = FutureProvider<List<Map<String, dynamic>>>((ref) async {
  final status = ref.watch(backendConnectionProvider);
  if (status.state != BackendConnectionState.connected) return [];
  return ref.watch(apiClientProvider).listJobs();
});

class HighlightsPage extends ConsumerStatefulWidget {
  const HighlightsPage({super.key});

  @override
  ConsumerState<HighlightsPage> createState() => _HighlightsPageState();
}

class _HighlightsPageState extends ConsumerState<HighlightsPage> {
  String? _message;
  bool _busy = false;

  Future<void> _runPipeline(String mediaId) async {
    setState(() {
      _busy = true;
      _message = 'Queueing transcription → analysis → highlights…';
    });
    final api = ref.read(apiClientProvider);
    try {
      await api.enqueueTranscription(mediaId);
      setState(() => _message = 'Transcription queued. Waiting for completion…');
      await _waitForJobType('transcribe_media');
      await api.enqueueSemanticAnalysis(mediaId);
      setState(() => _message = 'Semantic analysis queued…');
      await _waitForJobType('semantic_analysis');
      await api.enqueueHighlightDetection(mediaId);
      setState(() => _message = 'Highlight detection queued…');
      await _waitForJobType('detect_highlights');
      setState(() => _message = 'Pipeline completed.');
      ref.invalidate(highlightsProvider);
      ref.invalidate(jobsProvider);
    } catch (error) {
      setState(() => _message = 'Pipeline failed: $error');
    } finally {
      setState(() => _busy = false);
    }
  }

  Future<void> _waitForJobType(String jobType) async {
    final api = ref.read(apiClientProvider);
    for (var i = 0; i < 180; i++) {
      await Future<void>.delayed(const Duration(seconds: 2));
      final jobs = await api.listJobs(limit: 20);
      final match = jobs.where((j) => j['job_type'] == jobType).toList();
      if (match.isEmpty) continue;
      final status = match.first['status'];
      if (status == 'completed') return;
      if (status == 'failed') {
        throw StateError(match.first['error_message']?.toString() ?? 'Job failed');
      }
    }
    throw StateError('Timed out waiting for $jobType');
  }

  @override
  Widget build(BuildContext context) {
    final backend = ref.watch(backendConnectionProvider);
    final highlights = ref.watch(highlightsProvider);
    final media = ref.watch(mediaListProvider);
    final jobs = ref.watch(jobsProvider);

    return Padding(
      padding: const EdgeInsets.all(28),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SectionHeader(
            title: 'AI Highlights',
            subtitle: 'Ranked moments from audio, speech, semantics, and visual change signals.',
          ),
          const SizedBox(height: 16),
          if (backend.state != BackendConnectionState.connected)
            const Text('Connect to the backend to review highlights.')
          else ...[
            Wrap(
              spacing: 12,
              runSpacing: 12,
              children: [
                media.when(
                  data: (items) {
                    if (items.isEmpty) {
                      return const Text('Import a video in Video Library first.');
                    }
                    return FilledButton.icon(
                      onPressed: _busy
                          ? null
                          : () => _runPipeline(items.first.id),
                      icon: const Icon(Icons.auto_awesome),
                      label: Text(
                        _busy
                            ? 'Processing…'
                            : 'Analyze latest import (${items.first.originalFilename})',
                      ),
                    );
                  },
                  loading: () => const CircularProgressIndicator(),
                  error: (e, _) => Text('$e'),
                ),
                OutlinedButton.icon(
                  onPressed: () {
                    ref.invalidate(highlightsProvider);
                    ref.invalidate(jobsProvider);
                  },
                  icon: const Icon(Icons.refresh),
                  label: const Text('Refresh'),
                ),
              ],
            ),
            if (_message != null) ...[
              const SizedBox(height: 10),
              Text(_message!, style: const TextStyle(color: AppTheme.textSecondary)),
            ],
            const SizedBox(height: 16),
            jobs.when(
              data: (items) {
                if (items.isEmpty) return const SizedBox.shrink();
                final latest = items.take(3).toList();
                return Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: AppTheme.surfaceAlt,
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(color: AppTheme.border),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Recent jobs', style: Theme.of(context).textTheme.titleSmall),
                      const SizedBox(height: 8),
                      for (final job in latest)
                        Text(
                          '${job['job_type']} · ${job['status']} · ${(job['progress'] as num?)?.toStringAsFixed(0) ?? '0'}% · ${job['current_stage'] ?? ''}',
                          style: const TextStyle(color: AppTheme.textSecondary),
                        ),
                    ],
                  ),
                );
              },
              loading: () => const SizedBox.shrink(),
              error: (_, __) => const SizedBox.shrink(),
            ),
            const SizedBox(height: 16),
            Expanded(
              child: highlights.when(
                data: (items) {
                  if (items.isEmpty) {
                    return const Center(
                      child: Text(
                        'No highlights yet. Run analysis on an imported video.',
                        style: TextStyle(color: AppTheme.textSecondary),
                      ),
                    );
                  }
                  return ListView.separated(
                    itemCount: items.length,
                    separatorBuilder: (_, __) => const SizedBox(height: 10),
                    itemBuilder: (context, index) {
                      final item = items[index];
                      final reasons = (item['detection_reasons'] as List?) ?? [];
                      return Container(
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
                          color: AppTheme.surfaceAlt,
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(color: AppTheme.border),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                Text(
                                  '#${index + 1}  score ${(item['score'] as num?)?.toStringAsFixed(3) ?? '0'}',
                                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                                        fontWeight: FontWeight.w700,
                                      ),
                                ),
                                const Spacer(),
                                Text(
                                  '${(item['start_seconds'] as num?)?.toStringAsFixed(1)}s → ${(item['end_seconds'] as num?)?.toStringAsFixed(1)}s',
                                  style: const TextStyle(color: AppTheme.textSecondary),
                                ),
                              ],
                            ),
                            const SizedBox(height: 8),
                            Text(
                              item['transcript_excerpt']?.toString().isNotEmpty == true
                                  ? item['transcript_excerpt'].toString()
                                  : 'No transcript excerpt',
                            ),
                            const SizedBox(height: 8),
                            Wrap(
                              spacing: 8,
                              runSpacing: 6,
                              children: [
                                for (final reason in reasons.take(6))
                                  Container(
                                    padding: const EdgeInsets.symmetric(
                                      horizontal: 8,
                                      vertical: 4,
                                    ),
                                    decoration: BoxDecoration(
                                      color: AppTheme.surface,
                                      borderRadius: BorderRadius.circular(8),
                                      border: Border.all(color: AppTheme.border),
                                    ),
                                    child: Text(
                                      reason is Map
                                          ? '${reason['signal']}: ${reason['value']}'
                                          : '$reason',
                                      style: Theme.of(context).textTheme.bodySmall,
                                    ),
                                  ),
                              ],
                            ),
                            const SizedBox(height: 10),
                            Row(
                              children: [
                                Text(
                                  'Status: ${item['status']}',
                                  style: const TextStyle(color: AppTheme.textSecondary),
                                ),
                                const Spacer(),
                                TextButton(
                                  onPressed: () async {
                                    await ref
                                        .read(apiClientProvider)
                                        .updateHighlightStatus(
                                          item['id'] as String,
                                          'accepted',
                                        );
                                    ref.invalidate(highlightsProvider);
                                  },
                                  child: const Text('Accept'),
                                ),
                                TextButton(
                                  onPressed: () async {
                                    await ref
                                        .read(apiClientProvider)
                                        .updateHighlightStatus(
                                          item['id'] as String,
                                          'rejected',
                                        );
                                    ref.invalidate(highlightsProvider);
                                  },
                                  child: const Text('Reject'),
                                ),
                              ],
                            ),
                          ],
                        ),
                      );
                    },
                  );
                },
                loading: () => const Center(child: CircularProgressIndicator()),
                error: (e, _) => Text('$e', style: const TextStyle(color: AppTheme.danger)),
              ),
            ),
          ],
        ],
      ),
    );
  }
}
