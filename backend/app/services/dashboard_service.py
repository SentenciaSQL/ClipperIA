"""Dashboard aggregation service."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.infrastructure.database.models import ProcessingStatus
from app.repositories.dashboard_repository import DashboardRepository
from app.services.system_detection import SystemDetectionService


class DashboardService:
    def __init__(
        self,
        db: Session,
        system_detection: SystemDetectionService | None = None,
    ) -> None:
        self._repo = DashboardRepository(db)
        self._system = system_detection or SystemDetectionService()

    def get_overview(self) -> dict[str, Any]:
        active_statuses = [
            ProcessingStatus.PENDING,
            ProcessingStatus.QUEUED,
            ProcessingStatus.RUNNING,
            ProcessingStatus.PAUSED,
        ]
        completed = self._repo.count_jobs_by_status([ProcessingStatus.COMPLETED])
        active = self._repo.count_jobs_by_status(active_statuses)
        system = self._system.detect_system()

        projects = [
            {
                "id": p.id,
                "name": p.name,
                "status": p.status,
                "updated_at": p.updated_at.isoformat() if p.updated_at else None,
            }
            for p in self._repo.recent_projects()
        ]
        streams = [
            {
                "id": s.id,
                "title": s.stream_title,
                "status": s.status,
                "started_at": s.started_at.isoformat() if s.started_at else None,
            }
            for s in self._repo.active_streams()
        ]

        return {
            "total_imported_videos": self._repo.count_media_assets(),
            "total_generated_clips": self._repo.count_clips(),
            "active_processing_jobs": active,
            "completed_jobs": completed,
            "recent_projects": projects,
            "active_streams": streams,
            "gpu": {
                "available": system.gpu.available,
                "name": system.gpu.name,
                "utilization_percent": system.gpu.utilization_percent,
                "vram_used_mb": system.gpu.vram_used_mb,
                "vram_total_mb": system.gpu.vram_total_mb,
            },
            "processing_statistics": {
                "cpu_count": system.cpu_count,
                "ram_available_mb": system.ram_available_mb,
                "ram_total_mb": system.ram_total_mb,
                "ffmpeg_available": system.ffmpeg.available,
            },
        }
