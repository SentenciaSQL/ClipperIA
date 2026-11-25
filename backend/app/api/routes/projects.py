"""Project management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import require_api_token
from app.infrastructure.database.session import get_db
from app.services.project_service import ProjectService

router = APIRouter(
    prefix="/projects",
    tags=["projects"],
    dependencies=[Depends(require_api_token)],
)


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class ProjectUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: str | None = None


@router.get("")
def list_projects(
    q: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[dict]:
    return ProjectService(db).list_projects(query=q)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_project(body: ProjectCreateRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return ProjectService(db).create_project(body.name, body.description)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{project_id}")
def get_project(project_id: str, db: Session = Depends(get_db)) -> dict:
    project = ProjectService(db).get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.patch("/{project_id}")
def update_project(
    project_id: str,
    body: ProjectUpdateRequest,
    db: Session = Depends(get_db),
) -> dict:
    try:
        return ProjectService(db).update_project(
            project_id,
            name=body.name,
            description=body.description,
            status=body.status,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: str, db: Session = Depends(get_db)) -> None:
    try:
        ProjectService(db).delete_project(project_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
