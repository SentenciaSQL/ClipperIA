"""Export center service."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.media.encoding import EXPORT_PRESETS, EncodeRequest, MediaEncoder
from app.repositories.clip_repository import ClipRepository
from app.repositories.media_repository import MediaRepository
from app.workers.job_manager import job_manager


class ExportService:
    def __init__(self, db: Session, settings: Settings | None = None) -> None:
        self._db = db
        self._settings = settings or get_settings()
        self._clips = ClipRepository(db)
        self._media = MediaRepository(db)
        self._encoder = MediaEncoder()

    def list_exports(self, clip_id: str | None = None) -> list[dict[str, Any]]:
        return [
            ClipRepository.serialize_export(e)
            for e in self._clips.list_exports(clip_id=clip_id)
        ]

    def get_export(self, export_id: str) -> dict[str, Any] | None:
        row = self._clips.get_export(export_id)
        return ClipRepository.serialize_export(row) if row else None

    def enqueue(
        self,
        clip_id: str,
        *,
        preset: str = "tiktok",
        fps: int | None = None,
    ) -> dict[str, Any]:
        clip = self._clips.get(clip_id)
        if clip is None:
            raise LookupError("Clip not found")
        if preset not in EXPORT_PRESETS:
            raise ValueError(f"Unknown preset '{preset}'")
        job = job_manager.enqueue(
            job_type="export_clip",
            project_id=clip.project_id,
            source_ref=clip_id,
            payload={"clip_id": clip_id, "preset": preset, "fps": fps},
        )
        from app.repositories.job_repository import JobRepository

        return JobRepository.serialize(job)

    def export_clip(
        self,
        clip_id: str,
        *,
        preset: str = "tiktok",
        fps: int | None = None,
        progress: Callable[[float, str], None] | None = None,
    ) -> dict[str, Any]:
        clip = self._clips.get(clip_id)
        if clip is None:
            raise LookupError("Clip not found")
        asset = self._media.get(clip.media_asset_id)
        if asset is None:
            raise LookupError("Media asset not found")
        if preset not in EXPORT_PRESETS:
            raise ValueError(f"Unknown preset '{preset}'")
        preset_cfg = EXPORT_PRESETS[preset]

        def report(value: float, stage: str) -> None:
            if progress:
                progress(value, stage)

        report(10, "preparing_export")
        export_id = str(uuid4())
        out = self._settings.exports_dir / export_id / f"{preset}_{export_id}.mp4"
        source = Path(clip.file_path) if clip.file_path and Path(clip.file_path).is_file() else Path(asset.file_path)
        width, height = map(int, str(preset_cfg["resolution"]).split("x"))

        # If exporting from already-rendered clip file, re-encode whole file to preset.
        start = 0.0 if source == Path(clip.file_path or "") else float(clip.start_seconds)
        end = (
            self._probe_duration(source)
            if source == Path(clip.file_path or "")
            else float(clip.end_seconds)
        )

        report(30, "encoding_export")
        self._encoder.encode(
            EncodeRequest(
                source=source if source == Path(asset.file_path) else Path(asset.file_path),
                destination=out,
                start_seconds=float(clip.start_seconds),
                end_seconds=float(clip.end_seconds),
                aspect_ratio=str(preset_cfg["aspect_ratio"]),
                width=width,
                height=height,
                fps=int(fps or preset_cfg["fps"]),
                video_bitrate=str(preset_cfg["video_bitrate"]),
                audio_bitrate=str(preset_cfg["audio_bitrate"]),
            )
        )
        report(90, "persisting")
        row = self._clips.add_export(
            id=export_id,
            clip_id=clip.id,
            preset=preset,
            aspect_ratio=str(preset_cfg["aspect_ratio"]),
            resolution=str(preset_cfg["resolution"]),
            file_path=str(out),
            status="completed",
            metadata_json={
                "fps": int(fps or preset_cfg["fps"]),
                "label": preset_cfg["label"],
                "source_start": start,
                "source_end": end,
            },
        )
        report(100, "completed")
        return ClipRepository.serialize_export(row)

    @staticmethod
    def _probe_duration(path: Path) -> float:
        from app.media.ffprobe import MediaProbeService

        try:
            return float(MediaProbeService().probe(path).duration_seconds or 0.0)
        except Exception:  # noqa: BLE001
            return 0.0
