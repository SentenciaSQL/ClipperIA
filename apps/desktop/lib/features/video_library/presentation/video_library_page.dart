import 'package:flutter/material.dart';

import '../../../shared/widgets/feature_placeholder_page.dart';

class VideoLibraryPage extends StatelessWidget {
  const VideoLibraryPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const FeaturePlaceholderPage(
      title: 'Video Library',
      description: 'Import, browse, and manage local video assets.',
      phaseLabel: 'Phase 2 — Media Ingestion & Library',
    );
  }
}
