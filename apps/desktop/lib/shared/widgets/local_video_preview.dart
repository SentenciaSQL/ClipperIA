import 'dart:io';

import 'package:flutter/material.dart';
import 'package:video_player/video_player.dart';

import '../../core/theme/app_theme.dart';

/// Embedded video preview for a local file path (Windows/desktop via fvp).
class LocalVideoPreview extends StatefulWidget {
  const LocalVideoPreview({
    super.key,
    required this.filePath,
    this.networkUrl,
  });

  final String? filePath;
  final String? networkUrl;

  @override
  State<LocalVideoPreview> createState() => _LocalVideoPreviewState();
}

class _LocalVideoPreviewState extends State<LocalVideoPreview> {
  VideoPlayerController? _controller;
  String? _error;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _init();
  }

  @override
  void didUpdateWidget(covariant LocalVideoPreview oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.filePath != widget.filePath ||
        oldWidget.networkUrl != widget.networkUrl) {
      _init();
    }
  }

  Future<void> _init() async {
    await _controller?.dispose();
    _controller = null;
    if (!mounted) return;
    setState(() {
      _loading = true;
      _error = null;
    });

    final path = widget.filePath;
    try {
      late final VideoPlayerController controller;
      if (path != null && path.isNotEmpty && File(path).existsSync()) {
        controller = VideoPlayerController.file(File(path));
      } else if (widget.networkUrl != null && widget.networkUrl!.isNotEmpty) {
        controller = VideoPlayerController.networkUrl(
          Uri.parse(widget.networkUrl!),
        );
      } else {
        setState(() {
          _loading = false;
          _error = 'No local clip file available yet.';
        });
        return;
      }
      await controller.initialize();
      await controller.setLooping(true);
      if (!mounted) {
        await controller.dispose();
        return;
      }
      setState(() {
        _controller = controller;
        _loading = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = 'Preview failed: $error';
      });
    }
  }

  @override
  void dispose() {
    _controller?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const ColoredBox(
        color: Colors.black,
        child: Center(child: CircularProgressIndicator()),
      );
    }
    if (_error != null || _controller == null || !_controller!.value.isInitialized) {
      return ColoredBox(
        color: Colors.black,
        child: Center(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Text(
              _error ?? 'Preview unavailable',
              textAlign: TextAlign.center,
              style: const TextStyle(color: AppTheme.textSecondary),
            ),
          ),
        ),
      );
    }

    final controller = _controller!;
    return ColoredBox(
      color: Colors.black,
      child: Stack(
        alignment: Alignment.center,
        children: [
          AspectRatio(
            aspectRatio: controller.value.aspectRatio == 0
                ? 16 / 9
                : controller.value.aspectRatio,
            child: VideoPlayer(controller),
          ),
          Positioned(
            bottom: 12,
            left: 12,
            right: 12,
            child: Row(
              children: [
                IconButton(
                  color: Colors.white,
                  onPressed: () {
                    setState(() {
                      if (controller.value.isPlaying) {
                        controller.pause();
                      } else {
                        controller.play();
                      }
                    });
                  },
                  icon: Icon(
                    controller.value.isPlaying ? Icons.pause : Icons.play_arrow,
                  ),
                ),
                Expanded(
                  child: VideoProgressIndicator(
                    controller,
                    allowScrubbing: true,
                    colors: const VideoProgressColors(
                      playedColor: AppTheme.accent,
                      bufferedColor: AppTheme.accentMuted,
                      backgroundColor: AppTheme.border,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
