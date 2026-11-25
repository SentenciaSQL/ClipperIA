import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/config/app_config.dart';
import 'core/services/backend_connection.dart';
import 'core/theme/app_theme.dart';
import 'routing/app_router.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const ProviderScope(child: AiClippingApp()));
}

class AiClippingApp extends ConsumerStatefulWidget {
  const AiClippingApp({super.key});

  @override
  ConsumerState<AiClippingApp> createState() => _AiClippingAppState();
}

class _AiClippingAppState extends ConsumerState<AiClippingApp> {
  late final _router = createAppRouter();

  @override
  void initState() {
    super.initState();
    Future.microtask(() {
      ref.read(backendConnectionProvider.notifier).connect();
    });
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: AppConfig.appName,
      debugShowCheckedModeBanner: false,
      theme: AppTheme.dark,
      routerConfig: _router,
    );
  }
}
