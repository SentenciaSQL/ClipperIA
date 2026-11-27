"""Live connections and sessions persistence."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.database.models import LiveSession, SourceConnection


class LiveRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def list_connections(self) -> list[SourceConnection]:
        stmt = select(SourceConnection).order_by(SourceConnection.created_at.desc())
        return list(self._db.scalars(stmt).all())

    def get_connection(self, connection_id: str) -> SourceConnection | None:
        return self._db.get(SourceConnection, connection_id)

    def create_connection(self, **kwargs: Any) -> SourceConnection:
        row = SourceConnection(**kwargs)
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return row

    def save_connection(self, row: SourceConnection) -> SourceConnection:
        self._db.commit()
        self._db.refresh(row)
        return row

    def delete_connection(self, row: SourceConnection) -> None:
        self._db.delete(row)
        self._db.commit()

    def list_sessions(self) -> list[LiveSession]:
        stmt = select(LiveSession).order_by(LiveSession.created_at.desc())
        return list(self._db.scalars(stmt).all())

    def get_session(self, session_id: str) -> LiveSession | None:
        return self._db.get(LiveSession, session_id)

    def create_session(self, **kwargs: Any) -> LiveSession:
        row = LiveSession(**kwargs)
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return row

    def save_session(self, row: LiveSession) -> LiveSession:
        self._db.commit()
        self._db.refresh(row)
        return row

    @staticmethod
    def serialize_connection(row: SourceConnection) -> dict[str, Any]:
        meta = dict(row.metadata_json or {})
        # Never return raw tokens to clients
        if "token" in meta:
            meta = {**meta, "token": {"present": True, "token_type": meta["token"].get("token_type")}}
        return {
            "id": row.id,
            "platform": row.platform,
            "display_name": row.display_name,
            "external_account_id": row.external_account_id,
            "credential_ref": row.credential_ref,
            "is_active": row.is_active,
            "metadata": meta,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }

    @staticmethod
    def serialize_session(row: LiveSession) -> dict[str, Any]:
        return {
            "id": row.id,
            "source_connection_id": row.source_connection_id,
            "stream_title": row.stream_title,
            "stream_url": row.stream_url,
            "status": row.status,
            "started_at": row.started_at.isoformat() if row.started_at else None,
            "ended_at": row.ended_at.isoformat() if row.ended_at else None,
            "recording_path": row.recording_path,
            "metadata": row.metadata_json,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
