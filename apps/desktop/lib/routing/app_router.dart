import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../features/clip_editor/presentation/clip_editor_page.dart';
import '../features/dashboard/presentation/dashboard_page.dart';
import '../features/exports/presentation/exports_page.dart';
import '../features/highlights/presentation/highlights_page.dart';
import '../features/live_monitor/presentation/live_monitor_page.dart';
import '../features/settings/presentation/settings_page.dart';
import '../features/video_library/presentation/video_library_page.dart';
import '../shared/widgets/app_shell.dart';

final GlobalKey<NavigatorState> _rootNavigatorKey = GlobalKey<NavigatorState>();

GoRouter createAppRouter() {
  return GoRouter(
    navigatorKey: _rootNavigatorKey,
    initialLocation: '/dashboard',
    routes: [
      ShellRoute(
        builder: (context, state, child) => AppShell(child: child),
        routes: [
          GoRoute(
            path: '/dashboard',
            name: 'dashboard',
            builder: (context, state) => const DashboardPage(),
          ),
          GoRoute(
            path: '/library',
            name: 'library',
            builder: (context, state) => const VideoLibraryPage(),
          ),
          GoRoute(
            path: '/live',
            name: 'live',
            builder: (context, state) => const LiveMonitorPage(),
          ),
          GoRoute(
            path: '/highlights',
            name: 'highlights',
            builder: (context, state) => const HighlightsPage(),
          ),
          GoRoute(
            path: '/editor',
            name: 'editor',
            builder: (context, state) => const ClipEditorPage(),
          ),
          GoRoute(
            path: '/exports',
            name: 'exports',
            builder: (context, state) => const ExportsPage(),
          ),
          GoRoute(
            path: '/settings',
            name: 'settings',
            builder: (context, state) => const SettingsPage(),
          ),
        ],
      ),
    ],
  );
}
