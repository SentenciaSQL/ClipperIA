"""Project persistence."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.database.models import Project


class ProjectRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def list(self, *, query: str | None = None) -> list[Project]:
        stmt = select(Project).order_by(Project.updated_at.desc())
        if query:
            like = f"%{query.strip()}%"
            stmt = stmt.where(Project.name.ilike(like))
        return list(self._db.scalars(stmt).all())

    def get(self, project_id: str) -> Project | None:
        return self._db.get(Project, project_id)

    def create(self, name: str, description: str | None = None) -> Project:
        project = Project(name=name.strip(), description=description)
        self._db.add(project)
        self._db.commit()
        self._db.refresh(project)
        return project

    def update(
        self,
        project: Project,
        *,
        name: str | None = None,
        description: str | None = None,
        status: str | None = None,
    ) -> Project:
        if name is not None:
            project.name = name.strip()
        if description is not None:
            project.description = description
        if status is not None:
            project.status = status
        self._db.commit()
        self._db.refresh(project)
        return project

    def delete(self, project: Project) -> None:
        self._db.delete(project)
        self._db.commit()
