import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/services/backend_connection.dart';
import '../../core/theme/app_theme.dart';

class AppShell extends ConsumerWidget {
  const AppShell({super.key, required this.child});

  final Widget child;

  static const _destinations = <_NavItem>[
    _NavItem('Dashboard', Icons.dashboard_outlined, '/dashboard'),
    _NavItem('Video Library', Icons.video_library_outlined, '/library'),
    _NavItem('Live Monitor', Icons.sensors_outlined, '/live'),
    _NavItem('AI Highlights', Icons.auto_awesome_outlined, '/highlights'),
    _NavItem('Clip Editor', Icons.content_cut_outlined, '/editor'),
    _NavItem('Export Center', Icons.ios_share_outlined, '/exports'),
    _NavItem('Settings', Icons.settings_outlined, '/settings'),
  ];

  int _indexForLocation(String location) {
    final match = _destinations.indexWhere((item) => location.startsWith(item.path));
    return match < 0 ? 0 : match;
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final location = GoRouterState.of(context).uri.toString();
    final selected = _indexForLocation(location);
    final backend = ref.watch(backendConnectionProvider);

    return Scaffold(
      body: Row(
        children: [
          NavigationRail(
            selectedIndex: selected,
            extended: MediaQuery.sizeOf(context).width >= 1180,
            onDestinationSelected: (index) => context.go(_destinations[index].path),
            leading: Padding(
              padding: const EdgeInsets.fromLTRB(12, 16, 12, 24),
              child: Column(
                children: [
                  Container(
                    width: 42,
                    height: 42,
                    decoration: BoxDecoration(
                      color: AppTheme.accent.withOpacity(0.15),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: AppTheme.accent.withOpacity(0.4)),
                    ),
                    child: const Icon(Icons.movie_filter_rounded, color: AppTheme.accent),
                  ),
                  const SizedBox(height: 10),
                  Text(
                    'AI Clipping',
                    style: Theme.of(context).textTheme.titleSmall?.copyWith(
                          fontWeight: FontWeight.w700,
                          letterSpacing: 0.2,
                        ),
                  ),
                ],
              ),
            ),
            destinations: [
              for (final item in _destinations)
                NavigationRailDestination(
                  icon: Icon(item.icon),
                  selectedIcon: Icon(item.icon, color: AppTheme.accent),
                  label: Text(item.label),
                ),
            ],
          ),
          const VerticalDivider(width: 1),
          Expanded(
            child: Column(
              children: [
                _TopBar(backend: backend),
                const Divider(height: 1),
                Expanded(child: child),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _TopBar extends ConsumerWidget {
  const _TopBar({required this.backend});

  final BackendStatus backend;

  Color get _statusColor {
    switch (backend.state) {
      case BackendConnectionState.connected:
        return AppTheme.accent;
      case BackendConnectionState.connecting:
        return AppTheme.warning;
      case BackendConnectionState.error:
        return AppTheme.danger;
      case BackendConnectionState.disconnected:
        return AppTheme.textSecondary;
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Container(
      height: 56,
      color: AppTheme.surface,
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Row(
        children: [
          Text(
            'AI Clipping Platform',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w600,
                ),
          ),
          const Spacer(),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              color: AppTheme.surfaceAlt,
              borderRadius: BorderRadius.circular(999),
              border: Border.all(color: AppTheme.border),
            ),
            child: Row(
              children: [
                Container(
                  width: 8,
                  height: 8,
                  decoration: BoxDecoration(color: _statusColor, shape: BoxShape.circle),
                ),
                const SizedBox(width: 8),
                Text(
                  backend.state == BackendConnectionState.connected
                      ? 'Backend online'
                      : (backend.message ?? 'Backend offline'),
                  style: Theme.of(context).textTheme.bodySmall,
                ),
                if (backend.websocketConnected) ...[
                  const SizedBox(width: 10),
                  const Icon(Icons.bolt, size: 14, color: AppTheme.accent),
                  const SizedBox(width: 2),
                  Text('WS', style: Theme.of(context).textTheme.bodySmall),
                ],
              ],
            ),
          ),
          const SizedBox(width: 12),
          OutlinedButton.icon(
            onPressed: () => ref.read(backendConnectionProvider.notifier).connect(),
            icon: const Icon(Icons.refresh, size: 16),
            label: const Text('Reconnect'),
          ),
        ],
      ),
    );
  }
}

class _NavItem {
  const _NavItem(this.label, this.icon, this.path);

  final String label;
  final IconData icon;
  final String path;
}
