"""Persistence for clip audio tracks."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.database.models import ClipAudioTrack


class AudioTrackRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get(self, track_id: str) -> ClipAudioTrack | None:
        return self._db.get(ClipAudioTrack, track_id)

    def list_for_clip(self, clip_id: str) -> list[ClipAudioTrack]:
        stmt = (
            select(ClipAudioTrack)
            .where(ClipAudioTrack.clip_id == clip_id)
            .order_by(ClipAudioTrack.sort_order.asc(), ClipAudioTrack.created_at.asc())
        )
        return list(self._db.scalars(stmt).all())

    def create(self, **kwargs: Any) -> ClipAudioTrack:
        row = ClipAudioTrack(**kwargs)
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return row

    def save(self, row: ClipAudioTrack) -> ClipAudioTrack:
        self._db.commit()
        self._db.refresh(row)
        return row

    def delete(self, row: ClipAudioTrack) -> None:
        self._db.delete(row)
        self._db.commit()

    @staticmethod
    def serialize(row: ClipAudioTrack) -> dict[str, Any]:
        return {
            "id": row.id,
            "clip_id": row.clip_id,
            "name": row.name,
            "kind": row.kind,
            "file_path": row.file_path,
            "enabled": row.enabled,
            "muted": row.muted,
            "exclude_from_export": row.exclude_from_export,
            "volume": row.volume,
            "fade_in_seconds": row.fade_in_seconds,
            "fade_out_seconds": row.fade_out_seconds,
            "start_seconds": row.start_seconds,
            "trim_start_seconds": row.trim_start_seconds,
            "trim_end_seconds": row.trim_end_seconds,
            "sync_offset_seconds": row.sync_offset_seconds,
            "locked": row.locked,
            "sort_order": row.sort_order,
            "meta": row.meta_json,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
