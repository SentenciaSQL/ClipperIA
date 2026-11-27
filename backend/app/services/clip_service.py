"""Automatic clip generation and editing service."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.media.encoding import (
    ASPECT_RATIO_SIZES,
    DURATION_PRESETS,
    EXPORT_PRESETS,
    EncodeRequest,
    MediaEncoder,
)
from app.repositories.clip_repository import ClipRepository
from app.repositories.highlight_repository import HighlightRepository
from app.repositories.media_repository import MediaRepository
from app.workers.job_manager import job_manager

logger = get_logger(__name__)


class ClipService:
    def __init__(self, db: Session, settings: Settings | None = None) -> None:
        self._db = db
        self._settings = settings or get_settings()
        self._clips = ClipRepository(db)
        self._highlights = HighlightRepository(db)
        self._media = MediaRepository(db)
        self._encoder = MediaEncoder()

    def presets(self) -> dict[str, Any]:
        return {
            "aspect_ratios": list(ASPECT_RATIO_SIZES.keys()),
            "duration_presets": DURATION_PRESETS,
            "export_presets": EXPORT_PRESETS,
            "nvenc_available": self._encoder.has_nvenc(),
        }

    def list_clips(
        self,
        *,
        media_asset_id: str | None = None,
        project_id: str | None = None,
    ) -> list[dict[str, Any]]:
        return [
            ClipRepository.serialize_clip(c)
            for c in self._clips.list(media_asset_id=media_asset_id, project_id=project_id)
        ]

    def get_clip(self, clip_id: str) -> dict[str, Any] | None:
        clip = self._clips.get(clip_id)
        if clip is None:
            return None
        payload = ClipRepository.serialize_clip(clip)
        payload["versions"] = [
            ClipRepository.serialize_version(v) for v in self._clips.list_versions(clip_id)
        ]
        payload["subtitles"] = [
            ClipRepository.serialize_subtitle(s) for s in self._clips.list_subtitles(clip_id)
        ]
        payload["exports"] = [
            ClipRepository.serialize_export(e) for e in self._clips.list_exports(clip_id=clip_id)
        ]
        try:
            from app.services.editor_service import EditorService

            payload["editor_state"] = EditorService(self._db).get_editor(clip_id)
        except Exception:  # noqa: BLE001
            payload["editor_state"] = {"editor": clip.editor_json or {}, "audio_tracks": []}
        return payload

    def update_clip(
        self,
        clip_id: str,
        *,
        title: str | None = None,
        start_seconds: float | None = None,
        end_seconds: float | None = None,
        aspect_ratio: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        clip = self._clips.get(clip_id)
        if clip is None:
            raise LookupError("Clip not found")
        if title is not None:
            clip.title = title
        if start_seconds is not None:
            clip.start_seconds = float(start_seconds)
        if end_seconds is not None:
            clip.end_seconds = float(end_seconds)
        if aspect_ratio is not None:
            clip.aspect_ratio = aspect_ratio
        if status is not None:
            clip.status = status
        if clip.end_seconds <= clip.start_seconds:
            raise ValueError("end_seconds must be greater than start_seconds")
        return ClipRepository.serialize_clip(self._clips.save(clip))

    def enqueue_generate_from_highlights(
        self,
        media_asset_id: str,
        *,
        aspect_ratio: str = "9:16",
        max_duration: float = 30.0,
        limit: int = 5,
    ) -> dict[str, Any]:
        asset = self._media.get(media_asset_id)
        if asset is None:
            raise LookupError("Media asset not found")
        job = job_manager.enqueue(
            job_type="generate_clips",
            project_id=asset.project_id,
            source_ref=media_asset_id,
            payload={
                "media_asset_id": media_asset_id,
                "aspect_ratio": aspect_ratio,
                "max_duration": max_duration,
                "limit": limit,
            },
        )
        from app.repositories.job_repository import JobRepository

        return JobRepository.serialize(job)

    def enqueue_render_clip(
        self,
        clip_id: str,
        *,
        version_label: str = "render",
        settings: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        clip = self._clips.get(clip_id)
        if clip is None:
            raise LookupError("Clip not found")
        job = job_manager.enqueue(
            job_type="render_clip",
            project_id=clip.project_id,
            source_ref=clip_id,
            payload={
                "clip_id": clip_id,
                "version_label": version_label,
                "settings": settings or {},
            },
        )
        from app.repositories.job_repository import JobRepository

        return JobRepository.serialize(job)

    def generate_from_highlights(
        self,
        media_asset_id: str,
        *,
        aspect_ratio: str = "9:16",
        max_duration: float = 30.0,
        limit: int = 5,
        progress: Callable[[float, str], None] | None = None,
    ) -> list[dict[str, Any]]:
        asset = self._media.get(media_asset_id)
        if asset is None:
            raise LookupError("Media asset not found")
        source = Path(asset.file_path)
        if not source.is_file():
            raise FileNotFoundError("Media file missing")

        highlights = self._highlights.list_for_media(media_asset_id)[: max(1, limit)]
        if not highlights:
            raise ValueError("No highlights available for clip generation")

        def report(value: float, stage: str) -> None:
            if progress:
                progress(value, stage)

        created: list[dict[str, Any]] = []
        total = len(highlights)
        for index, highlight in enumerate(highlights):
            report(5 + (index / total) * 90, f"encoding_clip_{index + 1}")
            start = float(highlight.start_seconds)
            end = float(highlight.end_seconds)
            if end - start > max_duration:
                end = start + max_duration
            # Snap to nearest duration preset ceiling when close
            duration = end - start
            for preset in DURATION_PRESETS:
                if duration <= preset:
                    end = start + min(preset, float(asset.duration_seconds or preset))
                    break

            clip_id = str(uuid4())
            out = self._settings.clips_dir / clip_id / f"{clip_id}.mp4"
            self._encoder.encode(
                EncodeRequest(
                    source=source,
                    destination=out,
                    start_seconds=start,
                    end_seconds=end,
                    aspect_ratio=aspect_ratio,
                )
            )
            clip = self._clips.create(
                id=clip_id,
                project_id=asset.project_id,
                media_asset_id=asset.id,
                highlight_id=highlight.id,
                title=f"Clip {index + 1} — {asset.original_filename}",
                start_seconds=start,
                end_seconds=end,
                aspect_ratio=aspect_ratio,
                file_path=str(out),
                status="ready",
            )
            self._clips.add_version(
                clip_id=clip.id,
                version_label="auto",
                file_path=str(out),
                settings_json={"aspect_ratio": aspect_ratio, "max_duration": max_duration},
                is_primary=True,
            )
            created.append(ClipRepository.serialize_clip(clip))

        report(100, "completed")
        return created

    def enqueue_alternative_versions(
        self,
        clip_id: str,
        *,
        aspect_ratios: list[str] | None = None,
    ) -> dict[str, Any]:
        clip = self._clips.get(clip_id)
        if clip is None:
            raise LookupError("Clip not found")
        job = job_manager.enqueue(
            job_type="generate_clip_versions",
            project_id=clip.project_id,
            source_ref=clip_id,
            payload={
                "clip_id": clip_id,
                "aspect_ratios": aspect_ratios or ["9:16", "1:1", "16:9"],
            },
        )
        from app.repositories.job_repository import JobRepository

        return JobRepository.serialize(job)

    def generate_alternative_versions(
        self,
        clip_id: str,
        *,
        aspect_ratios: list[str] | None = None,
        progress: Callable[[float, str], None] | None = None,
    ) -> list[dict[str, Any]]:
        ratios = aspect_ratios or ["9:16", "1:1", "16:9"]
        created: list[dict[str, Any]] = []
        total = max(1, len(ratios))

        def report(value: float, stage: str) -> None:
            if progress:
                progress(value, stage)

        for index, ratio in enumerate(ratios):
            report((index / total) * 100, f"version_{ratio}")
            version = self.render_clip(
                clip_id,
                version_label=f"alt-{ratio.replace(':', 'x')}",
                settings={"aspect_ratio": ratio, "make_primary": False},
            )
            created.append(version)
        report(100, "completed")
        return created

    def render_clip(
        self,
        clip_id: str,
        *,
        version_label: str = "render",
        settings: dict[str, Any] | None = None,
        progress: Callable[[float, str], None] | None = None,
    ) -> dict[str, Any]:
        clip = self._clips.get(clip_id)
        if clip is None:
            raise LookupError("Clip not found")
        asset = self._media.get(clip.media_asset_id)
        if asset is None:
            raise LookupError("Media asset not found")
        source = Path(asset.file_path)
        settings = settings or {}
        make_primary = bool(settings.get("make_primary", True))

        def report(value: float, stage: str) -> None:
            if progress:
                progress(value, stage)

        report(10, "encoding")
        version_id = str(uuid4())
        out = self._settings.clips_dir / clip.id / f"{version_id}.mp4"
        from app.services.editor_service import EditorService

        # Persist any editor overrides passed from the UI before composing
        editor_patch = {
            k: settings[k]
            for k in (
                "opacity",
                "opacity_keyframes",
                "zoom",
                "crop_box",
                "master_volume",
                "normalize_audio",
                "burn_captions",
                "ducking",
            )
            if k in settings
        }
        if editor_patch:
            EditorService(self._db).update_editor(clip_id, editor_patch)
        encode_req = EditorService(self._db).build_encode_request(
            clip_id,
            destination=out,
            settings=settings,
        )
        # Legacy single audio_path still honored when no mix tracks beyond original
        if settings.get("audio_path") and not encode_req.audio_mix:
            audio = Path(settings["audio_path"])
            if audio.is_file():
                encode_req.audio_source = audio
                encode_req.include_source_audio = False
        self._encoder.encode(encode_req)
        report(85, "persisting")
        if make_primary:
            if settings.get("start_seconds") is not None:
                clip.start_seconds = float(settings["start_seconds"])
            if settings.get("end_seconds") is not None:
                clip.end_seconds = float(settings["end_seconds"])
            if settings.get("aspect_ratio") is not None:
                clip.aspect_ratio = str(settings["aspect_ratio"])
            clip.file_path = str(out)
            clip.status = "ready"
            self._clips.save(clip)
        version = self._clips.add_version(
            clip_id=clip.id,
            version_label=version_label,
            file_path=str(out),
            settings_json=settings,
            is_primary=make_primary,
        )
        report(100, "completed")
        return ClipRepository.serialize_version(version)
