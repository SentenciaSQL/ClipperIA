"""Transcript persistence."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.database.models import Transcript


class TranscriptRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get(self, transcript_id: str) -> Transcript | None:
        return self._db.get(Transcript, transcript_id)

    def latest_for_media(self, media_asset_id: str) -> Transcript | None:
        stmt = (
            select(Transcript)
            .where(Transcript.media_asset_id == media_asset_id)
            .order_by(Transcript.created_at.desc())
            .limit(1)
        )
        return self._db.scalar(stmt)

    def create(self, **kwargs: Any) -> Transcript:
        row = Transcript(**kwargs)
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return row

    def save(self, row: Transcript) -> Transcript:
        self._db.commit()
        self._db.refresh(row)
        return row

    @staticmethod
    def serialize(row: Transcript) -> dict[str, Any]:
        return {
            "id": row.id,
            "media_asset_id": row.media_asset_id,
            "language": row.language,
            "full_text": row.full_text,
            "segments": row.segments_json,
            "model_name": row.model_name,
            "status": row.status,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
