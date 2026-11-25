"""Project application service."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.repositories.project_repository import ProjectRepository


class ProjectService:
    def __init__(self, db: Session) -> None:
        self._repo = ProjectRepository(db)

    def list_projects(self, query: str | None = None) -> list[dict[str, Any]]:
        return [self._serialize(p) for p in self._repo.list(query=query)]

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        project = self._repo.get(project_id)
        return self._serialize(project) if project else None

    def create_project(self, name: str, description: str | None = None) -> dict[str, Any]:
        if not name.strip():
            raise ValueError("Project name is required")
        return self._serialize(self._repo.create(name=name, description=description))

    def update_project(
        self,
        project_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        project = self._repo.get(project_id)
        if project is None:
            raise LookupError("Project not found")
        return self._serialize(
            self._repo.update(
                project,
                name=name,
                description=description,
                status=status,
            )
        )

    def delete_project(self, project_id: str) -> None:
        project = self._repo.get(project_id)
        if project is None:
            raise LookupError("Project not found")
        self._repo.delete(project)

    @staticmethod
    def _serialize(project: Any) -> dict[str, Any]:
        return {
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "status": project.status,
            "created_at": project.created_at.isoformat() if project.created_at else None,
            "updated_at": project.updated_at.isoformat() if project.updated_at else None,
        }
