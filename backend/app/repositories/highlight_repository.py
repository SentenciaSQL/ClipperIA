"""Highlight persistence."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.database.models import Highlight


class HighlightRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get(self, highlight_id: str) -> Highlight | None:
        return self._db.get(Highlight, highlight_id)

    def list_for_media(self, media_asset_id: str) -> list[Highlight]:
        stmt = (
            select(Highlight)
            .where(Highlight.media_asset_id == media_asset_id)
            .order_by(Highlight.score.desc(), Highlight.start_seconds.asc())
        )
        return list(self._db.scalars(stmt).all())

    def list_all(self, *, limit: int = 200) -> list[Highlight]:
        stmt = (
            select(Highlight)
            .order_by(Highlight.score.desc(), Highlight.created_at.desc())
            .limit(limit)
        )
        return list(self._db.scalars(stmt).all())

    def delete_for_media(self, media_asset_id: str) -> int:
        rows = self.list_for_media(media_asset_id)
        for row in rows:
            self._db.delete(row)
        self._db.commit()
        return len(rows)

    def create(self, **kwargs: Any) -> Highlight:
        row = Highlight(**kwargs)
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return row

    def save(self, row: Highlight) -> Highlight:
        self._db.commit()
        self._db.refresh(row)
        return row

    @staticmethod
    def serialize(row: Highlight) -> dict[str, Any]:
        return {
            "id": row.id,
            "media_asset_id": row.media_asset_id,
            "start_seconds": row.start_seconds,
            "end_seconds": row.end_seconds,
            "score": row.score,
            "transcript_excerpt": row.transcript_excerpt,
            "detection_reasons": row.detection_reasons_json,
            "source_ref": row.source_ref,
            "status": row.status,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
