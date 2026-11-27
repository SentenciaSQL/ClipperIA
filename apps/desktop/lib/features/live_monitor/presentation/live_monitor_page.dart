import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/services/backend_connection.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets/section_header.dart';

final livePlatformsProvider = FutureProvider<Map<String, dynamic>>((ref) async {
  final status = ref.watch(backendConnectionProvider);
  if (status.state != BackendConnectionState.connected) return {};
  return ref.watch(apiClientProvider).getLivePlatforms();
});

final liveConnectionsProvider =
    FutureProvider<List<Map<String, dynamic>>>((ref) async {
  final status = ref.watch(backendConnectionProvider);
  if (status.state != BackendConnectionState.connected) return [];
  return ref.watch(apiClientProvider).listLiveConnections();
});

final liveSessionsProvider =
    FutureProvider<List<Map<String, dynamic>>>((ref) async {
  final status = ref.watch(backendConnectionProvider);
  if (status.state != BackendConnectionState.connected) return [];
  return ref.watch(apiClientProvider).listLiveSessions();
});

class LiveMonitorPage extends ConsumerStatefulWidget {
  const LiveMonitorPage({super.key});

  @override
  ConsumerState<LiveMonitorPage> createState() => _LiveMonitorPageState();
}

class _LiveMonitorPageState extends ConsumerState<LiveMonitorPage> {
  String _platform = 'twitch';
  final _nameController = TextEditingController(text: 'My channel');
  final _captureController = TextEditingController();
  String? _selectedConnectionId;
  String? _message;
  bool _busy = false;

  @override
  void dispose() {
    _nameController.dispose();
    _captureController.dispose();
    super.dispose();
  }

  Future<void> _addConnection() async {
    setState(() => _busy = true);
    try {
      await ref.read(apiClientProvider).createLiveConnection(
            platform: _platform,
            displayName: _nameController.text.trim(),
          );
      ref.invalidate(liveConnectionsProvider);
      setState(() => _message = 'Connection created. Configure OAuth credentials to authorize.');
    } catch (error) {
      setState(() => _message = 'Create failed: $error');
    } finally {
      setState(() => _busy = false);
    }
  }

  Future<void> _startOAuth() async {
    setState(() => _busy = true);
    try {
      final result = await ref.read(apiClientProvider).startLiveOAuth(
            platform: _platform,
            redirectUri: 'http://127.0.0.1:8765/oauth/callback',
          );
      final url = result['authorize_url']?.toString() ?? '';
      await Clipboard.setData(ClipboardData(text: url));
      setState(
        () => _message =
            'OAuth URL copied to clipboard. Open it in a browser, then complete callback via API.',
      );
    } catch (error) {
      setState(() => _message = 'OAuth start failed: $error');
    } finally {
      setState(() => _busy = false);
    }
  }

  Future<void> _startCapture() async {
    if (_selectedConnectionId == null || _captureController.text.trim().isEmpty) {
      setState(() => _message = 'Select a connection and provide an authorized local AV input.');
      return;
    }
    setState(() => _busy = true);
    try {
      final session = await ref.read(apiClientProvider).startLocalCapture(
            connectionId: _selectedConnectionId!,
            inputUrl: _captureController.text.trim(),
            title: 'OBS / local capture',
          );
      setState(() => _message = 'Capture session ${session['id']} started.');
      ref.invalidate(liveSessionsProvider);
    } catch (error) {
      setState(() => _message = 'Capture failed: $error');
    } finally {
      setState(() => _busy = false);
    }
  }

  Future<void> _stop(String sessionId) async {
    await ref.read(apiClientProvider).stopLiveSession(sessionId);
    ref.invalidate(liveSessionsProvider);
  }

  Future<void> _highlights(String sessionId) async {
    setState(() => _busy = true);
    try {
      final job =
          await ref.read(apiClientProvider).enqueueLiveHighlights(sessionId);
      setState(() => _message = 'Live highlight job ${job['id']} queued.');
    } catch (error) {
      setState(() => _message = 'Live highlights failed: $error');
    } finally {
      setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final backend = ref.watch(backendConnectionProvider);
    final platforms = ref.watch(livePlatformsProvider);
    final connections = ref.watch(liveConnectionsProvider);
    final sessions = ref.watch(liveSessionsProvider);

    return Padding(
      padding: const EdgeInsets.all(28),
      child: ListView(
        children: [
          const SectionHeader(
            title: 'Live Monitor',
            subtitle:
                'YouTube / Twitch / Kick OAuth, stream status, chat when available, and authorized OBS/local capture.',
          ),
          const SizedBox(height: 16),
          if (backend.state != BackendConnectionState.connected)
            const Text('Connect to the backend to manage live sources.')
          else ...[
            platforms.when(
              data: (data) {
                return Wrap(
                  spacing: 10,
                  runSpacing: 10,
                  children: [
                    for (final entry in data.entries)
                      Container(
                        width: 260,
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: AppTheme.surfaceAlt,
                          borderRadius: BorderRadius.circular(10),
                          border: Border.all(color: AppTheme.border),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              entry.key.toUpperCase(),
                              style: const TextStyle(fontWeight: FontWeight.w700),
                            ),
                            const SizedBox(height: 6),
                            Text(
                              'OAuth configured: ${(entry.value as Map)['configured'] == true}',
                              style: const TextStyle(color: AppTheme.textSecondary),
                            ),
                            Text(
                              'Direct AV: ${(entry.value as Map)['direct_av'] == true}',
                              style: const TextStyle(color: AppTheme.textSecondary),
                            ),
                            const SizedBox(height: 6),
                            Text(
                              ((entry.value as Map)['capture'] as Map?)?['notes']?.toString() ??
                                  '',
                              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                    color: AppTheme.textSecondary,
                                  ),
                            ),
                          ],
                        ),
                      ),
                  ],
                );
              },
              loading: () => const LinearProgressIndicator(),
              error: (e, _) => Text('$e'),
            ),
            const SizedBox(height: 20),
            Wrap(
              spacing: 12,
              runSpacing: 12,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                DropdownButton<String>(
                  value: _platform,
                  items: const [
                    DropdownMenuItem(value: 'youtube', child: Text('YouTube')),
                    DropdownMenuItem(value: 'twitch', child: Text('Twitch')),
                    DropdownMenuItem(value: 'kick', child: Text('Kick')),
                  ],
                  onChanged: (v) => setState(() => _platform = v ?? 'twitch'),
                ),
                SizedBox(
                  width: 220,
                  child: TextField(
                    controller: _nameController,
                    decoration: const InputDecoration(labelText: 'Display name'),
                  ),
                ),
                FilledButton(
                  onPressed: _busy ? null : _addConnection,
                  child: const Text('Add connection'),
                ),
                OutlinedButton(
                  onPressed: _busy ? null : _startOAuth,
                  child: const Text('Start OAuth'),
                ),
              ],
            ),
            const SizedBox(height: 16),
            connections.when(
              data: (items) {
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Connections', style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: 8),
                    if (items.isEmpty)
                      const Text(
                        'No connections yet.',
                        style: TextStyle(color: AppTheme.textSecondary),
                      ),
                    for (final item in items)
                      RadioListTile<String>(
                        value: item['id'] as String,
                        groupValue: _selectedConnectionId,
                        onChanged: (v) => setState(() => _selectedConnectionId = v),
                        title: Text('${item['platform']} · ${item['display_name']}'),
                        subtitle: Text(item['credential_ref']?.toString() ?? 'no credential'),
                      ),
                  ],
                );
              },
              loading: () => const LinearProgressIndicator(),
              error: (e, _) => Text('$e'),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _captureController,
              decoration: const InputDecoration(
                labelText: 'Authorized local AV input (OBS URL/device/file)',
                hintText: 'Example: /dev/video0 or path to OBS recording',
              ),
            ),
            const SizedBox(height: 8),
            FilledButton.icon(
              onPressed: _busy ? null : _startCapture,
              icon: const Icon(Icons.fiber_manual_record),
              label: const Text('Start rolling capture'),
            ),
            if (_message != null) ...[
              const SizedBox(height: 10),
              Text(_message!, style: const TextStyle(color: AppTheme.textSecondary)),
            ],
            const SizedBox(height: 20),
            sessions.when(
              data: (items) {
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Sessions', style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: 8),
                    if (items.isEmpty)
                      const Text(
                        'No live sessions.',
                        style: TextStyle(color: AppTheme.textSecondary),
                      ),
                    for (final session in items)
                      Container(
                        margin: const EdgeInsets.only(bottom: 8),
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: AppTheme.surfaceAlt,
                          borderRadius: BorderRadius.circular(10),
                          border: Border.all(color: AppTheme.border),
                        ),
                        child: Row(
                          children: [
                            Expanded(
                              child: Text(
                                '${session['stream_title']} · ${session['status']}',
                              ),
                            ),
                            TextButton(
                              onPressed: () => _highlights(session['id'] as String),
                              child: const Text('Detect highlights'),
                            ),
                            TextButton(
                              onPressed: () => _stop(session['id'] as String),
                              child: const Text('Stop'),
                            ),
                          ],
                        ),
                      ),
                  ],
                );
              },
              loading: () => const LinearProgressIndicator(),
              error: (e, _) => Text('$e'),
            ),
          ],
        ],
      ),
    );
  }
}
