import 'package:flutter/material.dart';

import '../../../shared/widgets/feature_placeholder_page.dart';

class LiveMonitorPage extends StatelessWidget {
  const LiveMonitorPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const FeaturePlaceholderPage(
      title: 'Live Monitor',
      description: 'Monitor authorized YouTube, Twitch, and Kick streams.',
      phaseLabel: 'Phase 7 — Live Streaming Integration',
    );
  }
}
