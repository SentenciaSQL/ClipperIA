"""Media asset persistence."""

from __future__ import annotations

from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.infrastructure.database.models import MediaAsset


class MediaRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def list(
        self,
        *,
        project_id: str | None = None,
        query: str | None = None,
        status: str | None = None,
    ) -> list[MediaAsset]:
        stmt = select(MediaAsset).order_by(MediaAsset.created_at.desc())
        if project_id:
            stmt = stmt.where(MediaAsset.project_id == project_id)
        if status:
            stmt = stmt.where(MediaAsset.status == status)
        if query:
            like = f"%{query.strip()}%"
            stmt = stmt.where(
                or_(
                    MediaAsset.original_filename.ilike(like),
                    MediaAsset.video_codec.ilike(like),
                )
            )
        return list(self._db.scalars(stmt).all())

    def get(self, asset_id: str) -> MediaAsset | None:
        return self._db.get(MediaAsset, asset_id)

    def create(self, **kwargs: Any) -> MediaAsset:
        asset = MediaAsset(**kwargs)
        self._db.add(asset)
        self._db.commit()
        self._db.refresh(asset)
        return asset

    def save(self, asset: MediaAsset) -> MediaAsset:
        self._db.commit()
        self._db.refresh(asset)
        return asset

    def delete(self, asset: MediaAsset) -> None:
        self._db.delete(asset)
        self._db.commit()
