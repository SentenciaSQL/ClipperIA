"""Register job handlers for AI/media pipelines."""

from __future__ import annotations

from typing import Any, Callable

from sqlalchemy.orm import Session

from app.infrastructure.database.models import ProcessingJob
from app.services.batch_service import BatchService
from app.services.clip_service import ClipService
from app.services.export_service import ExportService
from app.services.highlight_service import HighlightService
from app.services.live_service import LiveService
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

    def generate_clips(
        db: Session,
        job: ProcessingJob,
        progress: Callable[[float, str], None],
    ) -> dict[str, Any]:
        payload = job.payload_json or {}
        media_id = payload.get("media_asset_id") or job.source_ref
        if not media_id:
            raise ValueError("media_asset_id required")
        rows = ClipService(db).generate_from_highlights(
            str(media_id),
            aspect_ratio=str(payload.get("aspect_ratio") or "9:16"),
            max_duration=float(payload.get("max_duration") or 30),
            limit=int(payload.get("limit") or 5),
            progress=progress,
        )
        return {"result_ref": media_id, "clip_count": len(rows)}

    def render_clip(
        db: Session,
        job: ProcessingJob,
        progress: Callable[[float, str], None],
    ) -> dict[str, Any]:
        payload = job.payload_json or {}
        clip_id = payload.get("clip_id") or job.source_ref
        if not clip_id:
            raise ValueError("clip_id required")
        version = ClipService(db).render_clip(
            str(clip_id),
            version_label=str(payload.get("version_label") or "render"),
            settings=payload.get("settings") or {},
            progress=progress,
        )
        return {"result_ref": version.get("id"), "version": version}

    def export_clip(
        db: Session,
        job: ProcessingJob,
        progress: Callable[[float, str], None],
    ) -> dict[str, Any]:
        payload = job.payload_json or {}
        clip_id = payload.get("clip_id") or job.source_ref
        if not clip_id:
            raise ValueError("clip_id required")
        row = ExportService(db).export_clip(
            str(clip_id),
            preset=str(payload.get("preset") or "tiktok"),
            fps=payload.get("fps"),
            progress=progress,
        )
        return {"result_ref": row.get("id"), "export": row}

    def live_highlight_pass(
        db: Session,
        job: ProcessingJob,
        progress: Callable[[float, str], None],
    ) -> dict[str, Any]:
        payload = job.payload_json or {}
        session_id = payload.get("session_id") or job.source_ref
        if not session_id:
            raise ValueError("session_id required")
        return LiveService(db).run_live_highlight_pass(str(session_id), progress=progress)

    def batch_process(
        db: Session,
        job: ProcessingJob,
        progress: Callable[[float, str], None],
    ) -> dict[str, Any]:
        payload = job.payload_json or {}
        media_ids = payload.get("media_asset_ids") or []
        if not media_ids and job.source_ref:
            media_ids = [job.source_ref]
        if not media_ids:
            raise ValueError("media_asset_ids required")
        result = BatchService(db).run(
            [str(m) for m in media_ids],
            profile_id=payload.get("profile_id"),
            progress=progress,
        )
        return {"result_ref": media_ids[0], "batch": result}

    def generate_clip_versions(
        db: Session,
        job: ProcessingJob,
        progress: Callable[[float, str], None],
    ) -> dict[str, Any]:
        payload = job.payload_json or {}
        clip_id = payload.get("clip_id") or job.source_ref
        if not clip_id:
            raise ValueError("clip_id required")
        versions = ClipService(db).generate_alternative_versions(
            str(clip_id),
            aspect_ratios=payload.get("aspect_ratios"),
            progress=progress,
        )
        return {"result_ref": clip_id, "versions": versions}

    manager.register("transcribe_media", transcribe)
    manager.register("semantic_analysis", semantic)
    manager.register("detect_highlights", highlights)
    manager.register("generate_clips", generate_clips)
    manager.register("render_clip", render_clip)
    manager.register("export_clip", export_clip)
    manager.register("live_highlight_pass", live_highlight_pass)
    manager.register("batch_process", batch_process)
    manager.register("generate_clip_versions", generate_clip_versions)
