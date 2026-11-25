import 'package:flutter/material.dart';

import '../../../shared/widgets/feature_placeholder_page.dart';

class ClipEditorPage extends StatelessWidget {
  const ClipEditorPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const FeaturePlaceholderPage(
      title: 'Clip Editor',
      description: 'Timeline editing, captions, reframing, and audio control.',
      phaseLabel: 'Phase 6 — Advanced Video Editing',
    );
  }
}
