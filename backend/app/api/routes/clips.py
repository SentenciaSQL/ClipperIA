"""Clip generation and editing endpoints."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import require_api_token
from app.infrastructure.database.session import get_db
from app.services.clip_service import ClipService
from app.services.export_service import ExportService
from app.services.subtitle_service import SubtitleService
from app.ai.reframing.face_tracker import FaceTracker
from app.media.demucs_separator import DemucsSeparator
from app.repositories.media_repository import MediaRepository
from app.core.config import get_settings

router = APIRouter(tags=["clips"], dependencies=[Depends(require_api_token)])


class GenerateClipsRequest(BaseModel):
    media_asset_id: str
    aspect_ratio: str = "9:16"
    max_duration: float = 30.0
    limit: int = Field(default=5, ge=1, le=20)


class ClipUpdateRequest(BaseModel):
    title: str | None = None
    start_seconds: float | None = None
    end_seconds: float | None = None
    aspect_ratio: str | None = None
    status: str | None = None


class RenderClipRequest(BaseModel):
    version_label: str = "edited"
    settings: dict = Field(default_factory=dict)


class ExportRequest(BaseModel):
    preset: str = "tiktok"
    fps: int | None = None


class SubtitleGenerateRequest(BaseModel):
    language: str = "en"
    style: dict | None = None


class SubtitleUpdateRequest(BaseModel):
    cues: list[dict]
    style: dict | None = None


@router.get("/clips/presets")
def clip_presets(db: Session = Depends(get_db)) -> dict:
    return ClipService(db).presets()


@router.get("/clips")
def list_clips(
    media_asset_id: str | None = Query(default=None),
    project_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[dict]:
    return ClipService(db).list_clips(media_asset_id=media_asset_id, project_id=project_id)


@router.get("/clips/{clip_id}")
def get_clip(clip_id: str, db: Session = Depends(get_db)) -> dict:
    clip = ClipService(db).get_clip(clip_id)
    if clip is None:
        raise HTTPException(status_code=404, detail="Clip not found")
    return clip


@router.patch("/clips/{clip_id}")
def update_clip(clip_id: str, body: ClipUpdateRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return ClipService(db).update_clip(clip_id, **body.model_dump(exclude_none=True))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/clips/generate", status_code=status.HTTP_202_ACCEPTED)
def generate_clips(body: GenerateClipsRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return ClipService(db).enqueue_generate_from_highlights(
            body.media_asset_id,
            aspect_ratio=body.aspect_ratio,
            max_duration=body.max_duration,
            limit=body.limit,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/clips/{clip_id}/render", status_code=status.HTTP_202_ACCEPTED)
def render_clip(clip_id: str, body: RenderClipRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return ClipService(db).enqueue_render_clip(
            clip_id,
            version_label=body.version_label,
            settings=body.settings,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/clips/{clip_id}/file")
def get_clip_file(clip_id: str, db: Session = Depends(get_db)) -> FileResponse:
    clip = ClipService(db).get_clip(clip_id)
    if clip is None or not clip.get("file_path"):
        raise HTTPException(status_code=404, detail="Clip file not found")
    path = Path(clip["file_path"])
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Clip file missing on disk")
    return FileResponse(path, media_type="video/mp4", filename=path.name)


@router.post("/clips/{clip_id}/subtitles")
def generate_subtitles(
    clip_id: str,
    body: SubtitleGenerateRequest = Body(default_factory=SubtitleGenerateRequest),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return SubtitleService(db).generate_from_transcript(
            clip_id, language=body.language, style=body.style
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/subtitles/{subtitle_id}")
def update_subtitles(
    subtitle_id: str,
    body: SubtitleUpdateRequest,
    db: Session = Depends(get_db),
) -> dict:
    try:
        return SubtitleService(db).update_cues(subtitle_id, body.cues, style=body.style)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/clips/{clip_id}/reframe")
def reframe_clip(clip_id: str, db: Session = Depends(get_db)) -> dict:
    clip = ClipService(db).get_clip(clip_id)
    if clip is None:
        raise HTTPException(status_code=404, detail="Clip not found")
    asset = MediaRepository(db).get(clip["media_asset_id"])
    if asset is None:
        raise HTTPException(status_code=404, detail="Media asset not found")
    result = FaceTracker().analyze_window(
        Path(asset.file_path),
        start_seconds=float(clip["start_seconds"]),
        end_seconds=float(clip["end_seconds"]),
        target_aspect=clip.get("aspect_ratio") or "9:16",
    )
    return result


@router.post("/clips/{clip_id}/separate-audio")
def separate_audio(clip_id: str, db: Session = Depends(get_db)) -> dict:
    clip = ClipService(db).get_clip(clip_id)
    if clip is None:
        raise HTTPException(status_code=404, detail="Clip not found")
    asset = MediaRepository(db).get(clip["media_asset_id"])
    if asset is None:
        raise HTTPException(status_code=404, detail="Media asset not found")
    settings = get_settings()
    separator = DemucsSeparator()
    if not separator.available():
        raise HTTPException(
            status_code=501,
            detail="Demucs is not installed. Optional: pip install demucs",
        )
    try:
        result = separator.separate(
            Path(asset.file_path),
            settings.cache_dir / "demucs" / clip_id,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return result


@router.get("/exports")
def list_exports(clip_id: str | None = Query(default=None), db: Session = Depends(get_db)) -> list[dict]:
    return ExportService(db).list_exports(clip_id=clip_id)


@router.post("/clips/{clip_id}/export", status_code=status.HTTP_202_ACCEPTED)
def export_clip(clip_id: str, body: ExportRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return ExportService(db).enqueue(clip_id, preset=body.preset, fps=body.fps)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/exports/{export_id}")
def get_export(export_id: str, db: Session = Depends(get_db)) -> dict:
    row = ExportService(db).get_export(export_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Export not found")
    return row


@router.get("/exports/{export_id}/download")
def download_export(export_id: str, db: Session = Depends(get_db)) -> FileResponse:
    row = ExportService(db).get_export(export_id)
    if row is None or not row.get("file_path"):
        raise HTTPException(status_code=404, detail="Export not found")
    path = Path(row["file_path"])
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Export file missing")
    return FileResponse(path, media_type="video/mp4", filename=path.name)
