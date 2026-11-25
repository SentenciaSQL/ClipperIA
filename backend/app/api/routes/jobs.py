"""Processing job endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.security import require_api_token
from app.infrastructure.database.session import get_db
from app.repositories.job_repository import JobRepository

router = APIRouter(
    prefix="/jobs",
    tags=["jobs"],
    dependencies=[Depends(require_api_token)],
)


@router.get("")
def list_jobs(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[dict]:
    repo = JobRepository(db)
    return [JobRepository.serialize(j) for j in repo.list_recent(limit=limit)]


@router.get("/{job_id}")
def get_job(job_id: str, db: Session = Depends(get_db)) -> dict:
    job = JobRepository(db).get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobRepository.serialize(job)
