"""Repository queries for dashboard statistics."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.infrastructure.database.models import (
    Clip,
    LiveSession,
    MediaAsset,
    ProcessingJob,
    ProcessingStatus,
    Project,
)


class DashboardRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def count_media_assets(self) -> int:
        return int(self._db.scalar(select(func.count()).select_from(MediaAsset)) or 0)

    def count_clips(self) -> int:
        return int(self._db.scalar(select(func.count()).select_from(Clip)) or 0)

    def count_jobs_by_status(self, statuses: list[ProcessingStatus]) -> int:
        stmt = (
            select(func.count())
            .select_from(ProcessingJob)
            .where(ProcessingJob.status.in_(statuses))
        )
        return int(self._db.scalar(stmt) or 0)

    def recent_projects(self, limit: int = 5) -> list[Project]:
        stmt = select(Project).order_by(Project.updated_at.desc()).limit(limit)
        return list(self._db.scalars(stmt).all())

    def active_streams(self) -> list[LiveSession]:
        stmt = select(LiveSession).where(LiveSession.status.in_(["live", "recording"]))
        return list(self._db.scalars(stmt).all())
