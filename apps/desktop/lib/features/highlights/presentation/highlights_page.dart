import 'package:flutter/material.dart';

import '../../../shared/widgets/feature_placeholder_page.dart';

class HighlightsPage extends StatelessWidget {
  const HighlightsPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const FeaturePlaceholderPage(
      title: 'AI Highlights',
      description: 'Review ranked moments detected by the analysis engine.',
      phaseLabel: 'Phase 4 — Highlight Detection Engine',
    );
  }
}
