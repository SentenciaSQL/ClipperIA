"""Clip / version / export / subtitle persistence."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.database.models import Clip, ClipVersion, Export, Subtitle


class ClipRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get(self, clip_id: str) -> Clip | None:
        return self._db.get(Clip, clip_id)

    def list(
        self,
        *,
        media_asset_id: str | None = None,
        project_id: str | None = None,
    ) -> list[Clip]:
        stmt = select(Clip).order_by(Clip.created_at.desc())
        if media_asset_id:
            stmt = stmt.where(Clip.media_asset_id == media_asset_id)
        if project_id:
            stmt = stmt.where(Clip.project_id == project_id)
        return list(self._db.scalars(stmt).all())

    def create(self, **kwargs: Any) -> Clip:
        row = Clip(**kwargs)
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return row

    def save(self, row: Clip) -> Clip:
        self._db.commit()
        self._db.refresh(row)
        return row

    def delete(self, row: Clip) -> None:
        self._db.delete(row)
        self._db.commit()

    def add_version(self, **kwargs: Any) -> ClipVersion:
        row = ClipVersion(**kwargs)
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return row

    def list_versions(self, clip_id: str) -> list[ClipVersion]:
        stmt = select(ClipVersion).where(ClipVersion.clip_id == clip_id).order_by(ClipVersion.created_at.desc())
        return list(self._db.scalars(stmt).all())

    def add_subtitle(self, **kwargs: Any) -> Subtitle:
        row = Subtitle(**kwargs)
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return row

    def list_subtitles(self, clip_id: str) -> list[Subtitle]:
        stmt = select(Subtitle).where(Subtitle.clip_id == clip_id).order_by(Subtitle.created_at.desc())
        return list(self._db.scalars(stmt).all())

    def get_subtitle(self, subtitle_id: str) -> Subtitle | None:
        return self._db.get(Subtitle, subtitle_id)

    def save_subtitle(self, row: Subtitle) -> Subtitle:
        self._db.commit()
        self._db.refresh(row)
        return row

    def add_export(self, **kwargs: Any) -> Export:
        row = Export(**kwargs)
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return row

    def list_exports(self, *, clip_id: str | None = None) -> list[Export]:
        stmt = select(Export).order_by(Export.created_at.desc())
        if clip_id:
            stmt = stmt.where(Export.clip_id == clip_id)
        return list(self._db.scalars(stmt).all())

    def get_export(self, export_id: str) -> Export | None:
        return self._db.get(Export, export_id)

    def save_export(self, row: Export) -> Export:
        self._db.commit()
        self._db.refresh(row)
        return row

    @staticmethod
    def serialize_clip(row: Clip) -> dict[str, Any]:
        return {
            "id": row.id,
            "project_id": row.project_id,
            "media_asset_id": row.media_asset_id,
            "highlight_id": row.highlight_id,
            "title": row.title,
            "start_seconds": row.start_seconds,
            "end_seconds": row.end_seconds,
            "aspect_ratio": row.aspect_ratio,
            "file_path": row.file_path,
            "status": row.status,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }

    @staticmethod
    def serialize_version(row: ClipVersion) -> dict[str, Any]:
        return {
            "id": row.id,
            "clip_id": row.clip_id,
            "version_label": row.version_label,
            "file_path": row.file_path,
            "settings": row.settings_json,
            "is_primary": row.is_primary,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    @staticmethod
    def serialize_subtitle(row: Subtitle) -> dict[str, Any]:
        return {
            "id": row.id,
            "clip_id": row.clip_id,
            "language": row.language,
            "file_path": row.file_path,
            "style": row.style_json,
            "content": row.content_json,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }

    @staticmethod
    def serialize_export(row: Export) -> dict[str, Any]:
        return {
            "id": row.id,
            "clip_id": row.clip_id,
            "preset": row.preset,
            "aspect_ratio": row.aspect_ratio,
            "resolution": row.resolution,
            "file_path": row.file_path,
            "status": row.status,
            "metadata": row.metadata_json,
            "download_url": f"/api/v1/exports/{row.id}/download" if row.file_path else None,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
