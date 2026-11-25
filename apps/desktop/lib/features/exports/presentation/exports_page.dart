import 'package:flutter/material.dart';

import '../../../shared/widgets/feature_placeholder_page.dart';

class ExportsPage extends StatelessWidget {
  const ExportsPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const FeaturePlaceholderPage(
      title: 'Export Center',
      description: 'Export clips for TikTok, Shorts, and Reels presets.',
      phaseLabel: 'Phase 5 — Automatic Clip Generation',
    );
  }
}
