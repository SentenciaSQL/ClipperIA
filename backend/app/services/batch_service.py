"""Batch automation workflows."""

from __future__ import annotations

from typing import Any, Callable

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.repositories.media_repository import MediaRepository
from app.services.clip_service import ClipService
from app.services.content_metadata_service import ContentMetadataService
from app.services.export_service import ExportService
from app.services.highlight_service import HighlightService
from app.services.profile_service import ProfileService
from app.services.semantic_analysis_service import SemanticAnalysisService
from app.services.subtitle_service import SubtitleService
from app.services.transcription_service import TranscriptionService
from app.ai.reframing.face_tracker import FaceTracker
from app.workers.job_manager import job_manager
from pathlib import Path

logger = get_logger(__name__)


class BatchService:
    def __init__(self, db: Session, settings: Settings | None = None) -> None:
        self._db = db
        self._settings = settings or get_settings()
        self._media = MediaRepository(db)

    def enqueue(
        self,
        media_asset_ids: list[str],
        *,
        profile_id: str | None = None,
    ) -> dict[str, Any]:
        if not media_asset_ids:
            raise ValueError("media_asset_ids required")
        for media_id in media_asset_ids:
            if self._media.get(media_id) is None:
                raise LookupError(f"Media asset not found: {media_id}")
        job = job_manager.enqueue(
            job_type="batch_process",
            source_ref=media_asset_ids[0],
            payload={
                "media_asset_ids": media_asset_ids,
                "profile_id": profile_id,
            },
        )
        from app.repositories.job_repository import JobRepository

        return JobRepository.serialize(job)

    def run(
        self,
        media_asset_ids: list[str],
        *,
        profile_id: str | None = None,
        progress: Callable[[float, str], None] | None = None,
    ) -> dict[str, Any]:
        profiles = ProfileService(self._db)
        if profile_id:
            try:
                profiles.set_active(profile_id)
            except LookupError:
                pass
        active = profiles.get_active()
        profile = active["profile"]

        def report(value: float, stage: str) -> None:
            if progress:
                progress(value, stage)

        results: list[dict[str, Any]] = []
        total = max(1, len(media_asset_ids))
        for index, media_id in enumerate(media_asset_ids):
            base = (index / total) * 100
            span = 100 / total
            item = self._process_one(
                media_id,
                profile,
                progress=lambda v, s, b=base, sp=span: report(b + (v / 100) * sp, s),
            )
            results.append(item)
        report(100, "completed")
        return {"profile": active, "results": results}

    def _process_one(
        self,
        media_id: str,
        profile: dict[str, Any],
        *,
        progress: Callable[[float, str], None],
    ) -> dict[str, Any]:
        progress(5, f"transcribe:{media_id}")
        TranscriptionService(self._db).transcribe_asset(
            media_id,
            model_size=str(profile.get("whisper_model_size") or self._settings.whisper_model_size),
            progress=lambda v, s: progress(5 + v * 0.2, s),
        )
        progress(30, f"analyze:{media_id}")
        try:
            SemanticAnalysisService(self._db).analyze_media(
                media_id,
                progress=lambda v, s: progress(30 + v * 0.15, s),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("batch_semantic_failed", media_id=media_id, error=str(exc))

        progress(50, f"highlights:{media_id}")
        highlights = HighlightService(self._db).detect_for_media(
            media_id,
            progress=lambda v, s: progress(50 + v * 0.15, s),
        )
        progress(70, f"clips:{media_id}")
        clips = ClipService(self._db).generate_from_highlights(
            media_id,
            aspect_ratio=str(profile.get("aspect_ratio") or "9:16"),
            max_duration=float(profile.get("max_duration") or 30),
            limit=int(profile.get("clip_limit") or 5),
            progress=lambda v, s: progress(70 + v * 0.15, s),
        )

        enriched = []
        for clip in clips:
            clip_id = clip["id"]
            if profile.get("generate_captions"):
                try:
                    SubtitleService(self._db).generate_from_transcript(clip_id)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("batch_captions_failed", clip_id=clip_id, error=str(exc))
            if profile.get("smart_reframe"):
                try:
                    asset = self._media.get(media_id)
                    if asset:
                        reframe = FaceTracker().analyze_window(
                            Path(asset.file_path),
                            start_seconds=float(clip["start_seconds"]),
                            end_seconds=float(clip["end_seconds"]),
                            target_aspect=str(clip.get("aspect_ratio") or "9:16"),
                        )
                        ClipService(self._db).render_clip(
                            clip_id,
                            version_label="batch-reframe",
                            settings={
                                "start_seconds": clip["start_seconds"],
                                "end_seconds": clip["end_seconds"],
                                "aspect_ratio": clip.get("aspect_ratio"),
                                "zoom": reframe.get("zoom", 1.2),
                                "crop_box": reframe.get("crop_box"),
                            },
                        )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("batch_reframe_failed", clip_id=clip_id, error=str(exc))
            metadata = None
            if profile.get("generate_metadata"):
                try:
                    metadata = ContentMetadataService(self._db).generate_for_clip(
                        clip_id,
                        provider=str(profile.get("ai_provider") or "auto"),
                        platform=str(profile.get("export_preset") or "tiktok"),
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("batch_metadata_failed", clip_id=clip_id, error=str(exc))
            export_row = None
            try:
                export_row = ExportService(self._db).export_clip(
                    clip_id,
                    preset=str(profile.get("export_preset") or "tiktok"),
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("batch_export_failed", clip_id=clip_id, error=str(exc))
            enriched.append(
                {
                    "clip": clip,
                    "metadata": metadata,
                    "export": export_row,
                }
            )

        progress(100, f"done:{media_id}")
        return {
            "media_asset_id": media_id,
            "highlight_count": len(highlights),
            "clips": enriched,
        }
