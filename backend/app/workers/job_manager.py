"""Persistent local job manager with concurrency controls."""

from __future__ import annotations

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.api.websocket import manager as ws_manager
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.infrastructure.database.models import ProcessingJob, ProcessingStatus
from app.infrastructure.database.session import SessionLocal
from app.repositories.job_repository import JobRepository

logger = get_logger(__name__)

JobHandler = Callable[[Session, ProcessingJob, Callable[[float, str], None]], dict[str, Any]]


class JobManager:
    """Queues jobs in SQLite and executes them on a bounded thread pool."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._handlers: dict[str, JobHandler] = {}
        self._executor = ThreadPoolExecutor(
            max_workers=max(1, self._settings.max_concurrent_jobs),
            thread_name_prefix="acp-job",
        )
        self._gpu_semaphore = threading.Semaphore(
            max(1, self._settings.max_gpu_inference_jobs)
        )
        self._loop: asyncio.AbstractEventLoop | None = None
        self._started = False

    def register(self, job_type: str, handler: JobHandler) -> None:
        self._handlers[job_type] = handler

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._started = True
        if self._settings.job_recovery_enabled:
            self.recover_interrupted()
        else:
            logger.info("job_recovery_disabled")
        self.pump()
        logger.info("job_manager_started")

    def shutdown(self) -> None:
        self._started = False
        self._executor.shutdown(wait=False, cancel_futures=True)
        logger.info("job_manager_shutdown")

    def enqueue(
        self,
        *,
        job_type: str,
        project_id: str | None = None,
        source_ref: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> ProcessingJob:
        db = SessionLocal()
        try:
            repo = JobRepository(db)
            job = repo.create(
                job_type=job_type,
                project_id=project_id,
                source_ref=source_ref,
                payload=payload or {},
                status=ProcessingStatus.QUEUED,
            )
            self._broadcast(
                {
                    "type": "job_queued",
                    "payload": JobRepository.serialize(job),
                }
            )
            self.pump()
            return job
        finally:
            db.close()

    def recover_interrupted(self) -> None:
        db = SessionLocal()
        try:
            repo = JobRepository(db)
            interrupted = repo.list_by_statuses(
                [ProcessingStatus.RUNNING, ProcessingStatus.PENDING]
            )
            for job in interrupted:
                repo.update_status(
                    job,
                    ProcessingStatus.QUEUED,
                    current_stage="recovered",
                    error_message=None,
                )
                logger.info("job_recovered", job_id=job.id, job_type=job.job_type)
        finally:
            db.close()

    def pump(self) -> None:
        if not self._started:
            return
        db = SessionLocal()
        try:
            repo = JobRepository(db)
            running = repo.count_by_status(ProcessingStatus.RUNNING)
            slots = max(0, self._settings.max_concurrent_jobs - running)
            if slots <= 0:
                return
            queued = repo.list_by_statuses([ProcessingStatus.QUEUED], limit=slots)
            for job in queued:
                repo.update_status(
                    job,
                    ProcessingStatus.RUNNING,
                    current_stage="starting",
                    started_at=datetime.now(timezone.utc),
                    progress=0.0,
                )
                self._broadcast(
                    {
                        "type": "job_started",
                        "payload": JobRepository.serialize(job),
                    }
                )
                self._executor.submit(self._run_job, job.id)
        finally:
            db.close()

    def acquire_gpu(self) -> None:
        self._gpu_semaphore.acquire()

    def release_gpu(self) -> None:
        self._gpu_semaphore.release()

    def _run_job(self, job_id: str) -> None:
        db = SessionLocal()
        try:
            repo = JobRepository(db)
            job = repo.get(job_id)
            if job is None:
                return
            handler = self._handlers.get(job.job_type)
            if handler is None:
                repo.update_status(
                    job,
                    ProcessingStatus.FAILED,
                    error_message=f"No handler for job type '{job.job_type}'",
                    completed_at=datetime.now(timezone.utc),
                )
                self._broadcast(
                    {
                        "type": "job_failed",
                        "payload": JobRepository.serialize(job),
                    }
                )
                return

            def progress(value: float, stage: str) -> None:
                fresh = repo.get(job_id)
                if fresh is None:
                    return
                repo.update_status(
                    fresh,
                    ProcessingStatus.RUNNING,
                    progress=max(0.0, min(100.0, value)),
                    current_stage=stage,
                )
                self._broadcast(
                    {
                        "type": "job_progress",
                        "payload": JobRepository.serialize(fresh),
                    }
                )

            try:
                result = handler(db, job, progress)
                fresh = repo.get(job_id)
                if fresh is None:
                    return
                repo.update_status(
                    fresh,
                    ProcessingStatus.COMPLETED,
                    progress=100.0,
                    current_stage="completed",
                    result_ref=str(result.get("result_ref")) if result else None,
                    completed_at=datetime.now(timezone.utc),
                    payload={**(fresh.payload_json or {}), "result": result},
                )
                self._broadcast(
                    {
                        "type": "job_completed",
                        "payload": JobRepository.serialize(fresh),
                    }
                )
            except Exception as exc:  # noqa: BLE001 - persist failure state
                logger.exception("job_failed", job_id=job_id)
                fresh = repo.get(job_id)
                if fresh is None:
                    return
                repo.update_status(
                    fresh,
                    ProcessingStatus.FAILED,
                    error_message=str(exc),
                    completed_at=datetime.now(timezone.utc),
                    current_stage="failed",
                )
                self._broadcast(
                    {
                        "type": "job_failed",
                        "payload": JobRepository.serialize(fresh),
                    }
                )
        finally:
            db.close()
            self.pump()

    def _broadcast(self, event: dict[str, Any]) -> None:
        if self._loop is None:
            return
        asyncio.run_coroutine_threadsafe(ws_manager.broadcast(event), self._loop)


job_manager = JobManager()
