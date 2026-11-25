"""Register job handlers for AI/media pipelines."""

from __future__ import annotations

from typing import Any, Callable

from sqlalchemy.orm import Session

from app.infrastructure.database.models import ProcessingJob
from app.services.highlight_service import HighlightService
from app.services.semantic_analysis_service import SemanticAnalysisService
from app.services.transcription_service import TranscriptionService
from app.workers.job_manager import JobManager


def register_handlers(manager: JobManager) -> None:
    def transcribe(
        db: Session,
        job: ProcessingJob,
        progress: Callable[[float, str], None],
    ) -> dict[str, Any]:
        payload = job.payload_json or {}
        media_id = payload.get("media_asset_id") or job.source_ref
        if not media_id:
            raise ValueError("media_asset_id required")
        result = TranscriptionService(db).transcribe_asset(
            str(media_id),
            model_size=payload.get("model_size"),
            progress=progress,
        )
        return {"result_ref": result.get("id"), "transcript_id": result.get("id")}

    def semantic(
        db: Session,
        job: ProcessingJob,
        progress: Callable[[float, str], None],
    ) -> dict[str, Any]:
        payload = job.payload_json or {}
        media_id = payload.get("media_asset_id") or job.source_ref
        if not media_id:
            raise ValueError("media_asset_id required")
        result = SemanticAnalysisService(db).analyze_media(str(media_id), progress=progress)
        return {"result_ref": media_id, "provider": result.get("provider")}

    def highlights(
        db: Session,
        job: ProcessingJob,
        progress: Callable[[float, str], None],
    ) -> dict[str, Any]:
        payload = job.payload_json or {}
        media_id = payload.get("media_asset_id") or job.source_ref
        if not media_id:
            raise ValueError("media_asset_id required")
        rows = HighlightService(db).detect_for_media(str(media_id), progress=progress)
        return {"result_ref": media_id, "highlight_count": len(rows)}

    manager.register("transcribe_media", transcribe)
    manager.register("semantic_analysis", semantic)
    manager.register("detect_highlights", highlights)
