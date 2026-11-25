"""Processing job persistence."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.infrastructure.database.models import ProcessingJob, ProcessingStatus


class JobRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get(self, job_id: str) -> ProcessingJob | None:
        return self._db.get(ProcessingJob, job_id)

    def create(
        self,
        *,
        job_type: str,
        project_id: str | None = None,
        source_ref: str | None = None,
        payload: dict[str, Any] | None = None,
        status: ProcessingStatus = ProcessingStatus.PENDING,
    ) -> ProcessingJob:
        job = ProcessingJob(
            job_type=job_type,
            project_id=project_id,
            source_ref=source_ref,
            payload_json=payload or {},
            status=status,
            progress=0.0,
        )
        self._db.add(job)
        self._db.commit()
        self._db.refresh(job)
        return job

    def list_by_statuses(
        self,
        statuses: list[ProcessingStatus],
        *,
        limit: int | None = None,
    ) -> list[ProcessingJob]:
        stmt = (
            select(ProcessingJob)
            .where(ProcessingJob.status.in_(statuses))
            .order_by(ProcessingJob.created_at.asc())
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self._db.scalars(stmt).all())

    def list_recent(self, *, limit: int = 50) -> list[ProcessingJob]:
        stmt = select(ProcessingJob).order_by(ProcessingJob.created_at.desc()).limit(limit)
        return list(self._db.scalars(stmt).all())

    def count_by_status(self, status: ProcessingStatus) -> int:
        stmt = (
            select(func.count())
            .select_from(ProcessingJob)
            .where(ProcessingJob.status == status)
        )
        return int(self._db.scalar(stmt) or 0)

    def update_status(
        self,
        job: ProcessingJob,
        status: ProcessingStatus,
        *,
        progress: float | None = None,
        current_stage: str | None = None,
        error_message: str | None = None,
        result_ref: str | None = None,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        payload: dict[str, Any] | None = None,
    ) -> ProcessingJob:
        job.status = status
        if progress is not None:
            job.progress = progress
        if current_stage is not None:
            job.current_stage = current_stage
        if error_message is not None:
            job.error_message = error_message
        if result_ref is not None:
            job.result_ref = result_ref
        if started_at is not None:
            job.started_at = started_at
        if completed_at is not None:
            job.completed_at = completed_at
        if payload is not None:
            job.payload_json = payload
        self._db.commit()
        self._db.refresh(job)
        return job

    @staticmethod
    def serialize(job: ProcessingJob) -> dict[str, Any]:
        return {
            "id": job.id,
            "job_type": job.job_type,
            "status": job.status.value if hasattr(job.status, "value") else str(job.status),
            "progress": job.progress,
            "current_stage": job.current_stage,
            "project_id": job.project_id,
            "source_ref": job.source_ref,
            "result_ref": job.result_ref,
            "error_message": job.error_message,
            "payload": job.payload_json,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        }
