"""Transcription orchestration service."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.ai.detection.silero_vad import SileroVadService
from app.ai.transcription.whisper_provider import FasterWhisperProvider
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.media.audio import extract_wav_mono_16k
from app.repositories.media_repository import MediaRepository
from app.repositories.transcript_repository import TranscriptRepository
from app.workers.job_manager import job_manager

logger = get_logger(__name__)


class TranscriptionService:
    def __init__(
        self,
        db: Session,
        settings: Settings | None = None,
    ) -> None:
        self._db = db
        self._settings = settings or get_settings()
        self._media = MediaRepository(db)
        self._transcripts = TranscriptRepository(db)
        self._whisper = FasterWhisperProvider(self._settings)
        self._vad = SileroVadService()

    def get_latest(self, media_asset_id: str) -> dict[str, Any] | None:
        row = self._transcripts.latest_for_media(media_asset_id)
        return TranscriptRepository.serialize(row) if row else None

    def enqueue(self, media_asset_id: str, *, model_size: str | None = None) -> dict[str, Any]:
        asset = self._media.get(media_asset_id)
        if asset is None:
            raise LookupError("Media asset not found")
        job = job_manager.enqueue(
            job_type="transcribe_media",
            project_id=asset.project_id,
            source_ref=asset.id,
            payload={
                "media_asset_id": media_asset_id,
                "model_size": model_size or self._settings.whisper_model_size,
            },
        )
        from app.repositories.job_repository import JobRepository

        return JobRepository.serialize(job)

    def transcribe_asset(
        self,
        media_asset_id: str,
        *,
        model_size: str | None = None,
        progress: Callable[[float, str], None] | None = None,
    ) -> dict[str, Any]:
        asset = self._media.get(media_asset_id)
        if asset is None:
            raise LookupError("Media asset not found")
        source = Path(asset.file_path)
        if not source.is_file():
            raise FileNotFoundError("Media file missing on disk")

        def report(value: float, stage: str) -> None:
            if progress:
                progress(value, stage)

        report(5, "extracting_audio")
        audio_path = self._settings.cache_dir / "audio" / f"{asset.id}.wav"
        extract_wav_mono_16k(source, audio_path)

        report(20, "voice_activity_detection")
        job_manager.acquire_gpu()
        try:
            vad_segments = self._vad.detect_speech_segments(audio_path)
            report(35, "transcribing")
            result = self._whisper.transcribe(
                str(audio_path),
                model_size=model_size or self._settings.whisper_model_size,
                vad_filter=True,
            )
        finally:
            job_manager.release_gpu()

        report(85, "persisting_transcript")
        row = self._transcripts.create(
            media_asset_id=asset.id,
            language=result.get("language"),
            full_text=result.get("full_text"),
            segments_json={
                "segments": result.get("segments") or [],
                "vad_segments": vad_segments,
                "language_probability": result.get("language_probability"),
                "duration": result.get("duration"),
                "device": result.get("device"),
            },
            model_name=result.get("model_name"),
            status="completed",
        )
        asset.status = "transcribed"
        self._media.save(asset)
        report(100, "completed")
        payload = TranscriptRepository.serialize(row)
        payload["vad_segments"] = vad_segments
        return payload
