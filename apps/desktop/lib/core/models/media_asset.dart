class MediaAsset {
  MediaAsset({
    required this.id,
    required this.originalFilename,
    required this.filePath,
    this.projectId,
    this.durationSeconds,
    this.width,
    this.height,
    this.frameRate,
    this.videoCodec,
    this.audioCodec,
    this.fileSizeBytes,
    this.thumbnailUrl,
    this.status,
    this.metadata,
    this.createdAt,
  });

  final String id;
  final String originalFilename;
  final String filePath;
  final String? projectId;
  final double? durationSeconds;
  final int? width;
  final int? height;
  final double? frameRate;
  final String? videoCodec;
  final String? audioCodec;
  final int? fileSizeBytes;
  final String? thumbnailUrl;
  final String? status;
  final Map<String, dynamic>? metadata;
  final String? createdAt;

  factory MediaAsset.fromJson(Map<String, dynamic> json) {
    return MediaAsset(
      id: json['id'] as String,
      originalFilename: json['original_filename'] as String? ?? 'video',
      filePath: json['file_path'] as String? ?? '',
      projectId: json['project_id'] as String?,
      durationSeconds: (json['duration_seconds'] as num?)?.toDouble(),
      width: json['width'] as int?,
      height: json['height'] as int?,
      frameRate: (json['frame_rate'] as num?)?.toDouble(),
      videoCodec: json['video_codec'] as String?,
      audioCodec: json['audio_codec'] as String?,
      fileSizeBytes: json['file_size_bytes'] as int?,
      thumbnailUrl: json['thumbnail_url'] as String?,
      status: json['status'] as String?,
      metadata: (json['metadata'] as Map?)?.cast<String, dynamic>(),
      createdAt: json['created_at'] as String?,
    );
  }

  String get resolutionLabel {
    if (width == null || height == null) return 'n/a';
    return '${width}x$height';
  }

  String get durationLabel {
    final total = durationSeconds ?? 0;
    final m = total ~/ 60;
    final s = (total % 60).floor().toString().padLeft(2, '0');
    return '$m:$s';
  }

  String get sizeLabel {
    final bytes = fileSizeBytes ?? 0;
    if (bytes < 1024 * 1024) return '${(bytes / 1024).toStringAsFixed(1)} KB';
    return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
  }
}

class ProjectItem {
  ProjectItem({
    required this.id,
    required this.name,
    this.description,
    this.status,
  });

  final String id;
  final String name;
  final String? description;
  final String? status;

  factory ProjectItem.fromJson(Map<String, dynamic> json) {
    return ProjectItem(
      id: json['id'] as String,
      name: json['name'] as String? ?? 'Project',
      description: json['description'] as String?,
      status: json['status'] as String?,
    );
  }
}
