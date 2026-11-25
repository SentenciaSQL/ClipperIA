"""Media library application service."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.media.ffprobe import MediaProbeError, MediaProbeService
from app.media.paths import thumbnail_path_for
from app.media.storage import copy_into_library, delete_asset_files, file_sha256
from app.media.thumbnails import ThumbnailError, ThumbnailService
from app.repositories.media_repository import MediaRepository
from app.repositories.project_repository import ProjectRepository

logger = get_logger(__name__)


class MediaService:
    def __init__(
        self,
        db: Session,
        settings: Settings | None = None,
        probe: MediaProbeService | None = None,
        thumbnails: ThumbnailService | None = None,
    ) -> None:
        self._db = db
        self._settings = settings or get_settings()
        self._repo = MediaRepository(db)
        self._projects = ProjectRepository(db)
        self._probe = probe or MediaProbeService()
        self._thumbnails = thumbnails or ThumbnailService()

    def list_media(
        self,
        *,
        project_id: str | None = None,
        query: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        return [
            self._serialize(a)
            for a in self._repo.list(project_id=project_id, query=query, status=status)
        ]

    def get_media(self, asset_id: str) -> dict[str, Any] | None:
        asset = self._repo.get(asset_id)
        return self._serialize(asset) if asset else None

    def import_local_file(
        self,
        source_path: str | Path,
        *,
        project_id: str | None = None,
        manage_original: bool = True,
        display_name: str | None = None,
    ) -> dict[str, Any]:
        source = Path(source_path).expanduser()
        if not source.is_file():
            raise FileNotFoundError(f"Source file not found: {source}")

        # Validate before copying
        probe = self._probe.probe(source)

        if project_id:
            if self._projects.get(project_id) is None:
                raise LookupError("Project not found")

        free = shutil.disk_usage(self._settings.data_root).free
        if probe.file_size_bytes * 1.15 > free:
            raise OSError("Insufficient disk space for media import")

        asset_id = str(uuid4())
        if manage_original:
            stored = copy_into_library(self._settings, source, asset_id)
        else:
            # Keep reference to user path; still require readable local file
            stored = source.resolve()

        checksum = file_sha256(stored)
        thumb_path = thumbnail_path_for(self._settings, asset_id)
        seek = 1.0 if (probe.duration_seconds or 0) > 2 else 0.0
        try:
            self._thumbnails.generate(stored, thumb_path, at_seconds=seek)
            thumbnail = str(thumb_path)
        except ThumbnailError as exc:
            logger.warning("thumbnail_failed", error=str(exc), asset_id=asset_id)
            thumbnail = None

        asset = self._repo.create(
            id=asset_id,
            project_id=project_id,
            file_path=str(stored),
            original_filename=display_name or source.name,
            media_type="video",
            duration_seconds=probe.duration_seconds,
            width=probe.width,
            height=probe.height,
            frame_rate=probe.frame_rate,
            video_codec=probe.video_codec,
            audio_codec=probe.audio_codec,
            file_size_bytes=probe.file_size_bytes,
            thumbnail_path=thumbnail,
            checksum=checksum,
            metadata_json={
                "format_name": probe.format_name,
                "creation_time": probe.creation_time,
                "audio_streams": probe.audio_streams,
                "managed_copy": manage_original,
                "source_path": str(source.resolve()),
            },
            status="imported",
        )
        logger.info("media_imported", asset_id=asset.id, path=asset.file_path)
        return self._serialize(asset)

    def reprocess(self, asset_id: str) -> dict[str, Any]:
        asset = self._repo.get(asset_id)
        if asset is None:
            raise LookupError("Media asset not found")
        path = Path(asset.file_path)
        if not path.is_file():
            raise FileNotFoundError("Media file missing on disk")

        probe = self._probe.probe(path)
        thumb_path = thumbnail_path_for(self._settings, asset.id)
        seek = 1.0 if (probe.duration_seconds or 0) > 2 else 0.0
        try:
            self._thumbnails.generate(path, thumb_path, at_seconds=seek)
            asset.thumbnail_path = str(thumb_path)
        except ThumbnailError as exc:
            logger.warning("thumbnail_failed", error=str(exc), asset_id=asset.id)

        asset.duration_seconds = probe.duration_seconds
        asset.width = probe.width
        asset.height = probe.height
        asset.frame_rate = probe.frame_rate
        asset.video_codec = probe.video_codec
        asset.audio_codec = probe.audio_codec
        asset.file_size_bytes = probe.file_size_bytes
        asset.checksum = file_sha256(path)
        meta = dict(asset.metadata_json or {})
        meta.update(
            {
                "format_name": probe.format_name,
                "creation_time": probe.creation_time,
                "audio_streams": probe.audio_streams,
            }
        )
        asset.metadata_json = meta
        asset.status = "imported"
        return self._serialize(self._repo.save(asset))

    def delete_media(self, asset_id: str, *, delete_files: bool = True) -> None:
        asset = self._repo.get(asset_id)
        if asset is None:
            raise LookupError("Media asset not found")

        file_path = Path(asset.file_path)
        thumb = Path(asset.thumbnail_path) if asset.thumbnail_path else None
        managed = bool((asset.metadata_json or {}).get("managed_copy", True))

        self._repo.delete(asset)

        if delete_files and managed:
            parent = file_path.parent if file_path.exists() else None
            delete_asset_files([file_path, thumb, parent])
        elif delete_files and thumb is not None:
            delete_asset_files([thumb])

    def _serialize(self, asset: Any) -> dict[str, Any]:
        return {
            "id": asset.id,
            "project_id": asset.project_id,
            "file_path": asset.file_path,
            "original_filename": asset.original_filename,
            "media_type": asset.media_type,
            "duration_seconds": asset.duration_seconds,
            "width": asset.width,
            "height": asset.height,
            "frame_rate": asset.frame_rate,
            "video_codec": asset.video_codec,
            "audio_codec": asset.audio_codec,
            "file_size_bytes": asset.file_size_bytes,
            "thumbnail_path": asset.thumbnail_path,
            "thumbnail_url": (
                f"/api/v1/media/{asset.id}/thumbnail" if asset.thumbnail_path else None
            ),
            "checksum": asset.checksum,
            "metadata": asset.metadata_json,
            "status": asset.status,
            "created_at": asset.created_at.isoformat() if asset.created_at else None,
            "updated_at": asset.updated_at.isoformat() if asset.updated_at else None,
        }
