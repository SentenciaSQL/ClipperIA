"""Advanced clip editor: audio tracks, captions, opacity."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import require_api_token
from app.infrastructure.database.session import get_db
from app.services.audio_track_service import AudioTrackService
from app.services.editor_service import EditorService
from app.services.subtitle_service import SubtitleService

router = APIRouter(tags=["editor"], dependencies=[Depends(require_api_token)])


class EditorPatchRequest(BaseModel):
    opacity: float | None = Field(default=None, ge=0, le=1)
    opacity_keyframes: list[dict[str, float]] | None = None
    zoom: float | None = None
    crop_box: dict[str, float] | None = None
    master_volume: float | None = Field(default=None, ge=0, le=2)
    normalize_audio: bool | None = None
    ducking: bool | None = None
    burn_captions: bool | None = None
    export_captions_sidecar: bool | None = None
    caption_preset: str | None = None
    active_subtitle_id: str | None = None


class AudioTrackCreateRequest(BaseModel):
    name: str
    kind: str = "music"
    file_path: str | None = None
    volume: float = 1.0
    start_seconds: float = 0.0


class AudioTrackUpdateRequest(BaseModel):
    name: str | None = None
    kind: str | None = None
    file_path: str | None = None
    enabled: bool | None = None
    muted: bool | None = None
    exclude_from_export: bool | None = None
    volume: float | None = None
    fade_in_seconds: float | None = None
    fade_out_seconds: float | None = None
    start_seconds: float | None = None
    trim_start_seconds: float | None = None
    trim_end_seconds: float | None = None
    sync_offset_seconds: float | None = None
    locked: bool | None = None
    sort_order: int | None = None
    meta: dict[str, Any] | None = None


class AudioImportRequest(BaseModel):
    path: str
    name: str | None = None
    kind: str = "music"


class CaptionUpdateRequest(BaseModel):
    cues: list[dict[str, Any]]
    style: dict[str, Any] | None = None
    preset: str | None = None


class WordOverrideRequest(BaseModel):
    cue_index: int
    override: dict[str, Any]


class CaptionGenerateRequest(BaseModel):
    language: str = "en"
    preset: str | None = "classic"
    style: dict[str, Any] | None = None
    replace_existing: bool = False


@router.get("/clips/{clip_id}/editor")
def get_editor(clip_id: str, db: Session = Depends(get_db)) -> dict:
    try:
        return EditorService(db).get_editor(clip_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/clips/{clip_id}/editor")
def patch_editor(clip_id: str, body: EditorPatchRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return EditorService(db).update_editor(
            clip_id, body.model_dump(exclude_none=True)
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/clips/{clip_id}/audio-tracks")
def list_audio_tracks(clip_id: str, db: Session = Depends(get_db)) -> list[dict]:
    try:
        return AudioTrackService(db).list_tracks(clip_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/clips/{clip_id}/audio-tracks", status_code=status.HTTP_201_CREATED)
def create_audio_track(
    clip_id: str, body: AudioTrackCreateRequest, db: Session = Depends(get_db)
) -> dict:
    try:
        AudioTrackService(db).ensure_original_track(clip_id)
        return AudioTrackService(db).create_track(
            clip_id,
            name=body.name,
            kind=body.kind,
            file_path=body.file_path,
            volume=body.volume,
            start_seconds=body.start_seconds,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/audio-tracks/{track_id}")
def update_audio_track(
    track_id: str, body: AudioTrackUpdateRequest, db: Session = Depends(get_db)
) -> dict:
    try:
        return AudioTrackService(db).update_track(
            track_id, body.model_dump(exclude_none=True)
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/audio-tracks/{track_id}/duplicate", status_code=status.HTTP_201_CREATED)
def duplicate_audio_track(track_id: str, db: Session = Depends(get_db)) -> dict:
    try:
        return AudioTrackService(db).duplicate_track(track_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/audio-tracks/{track_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_audio_track(track_id: str, db: Session = Depends(get_db)) -> None:
    try:
        AudioTrackService(db).delete_track(track_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/clips/{clip_id}/audio-tracks/import")
def import_audio_track(
    clip_id: str, body: AudioImportRequest, db: Session = Depends(get_db)
) -> dict:
    try:
        AudioTrackService(db).ensure_original_track(clip_id)
        return AudioTrackService(db).import_audio_file(
            clip_id, body.path, name=body.name, kind=body.kind
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/clips/{clip_id}/audio/separate", status_code=status.HTTP_202_ACCEPTED)
def separate_audio_job(clip_id: str, db: Session = Depends(get_db)) -> dict:
    try:
        return AudioTrackService(db).enqueue_demucs(clip_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc


@router.get("/captions/presets")
def caption_presets(db: Session = Depends(get_db)) -> dict:
    return SubtitleService(db).presets()


@router.post("/clips/{clip_id}/subtitles/advanced")
def generate_captions_advanced(
    clip_id: str, body: CaptionGenerateRequest, db: Session = Depends(get_db)
) -> dict:
    try:
        return SubtitleService(db).generate_from_transcript(
            clip_id,
            language=body.language,
            style=body.style,
            preset=body.preset,
            replace_existing=body.replace_existing,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/subtitles/{subtitle_id}/advanced")
def update_captions_advanced(
    subtitle_id: str, body: CaptionUpdateRequest, db: Session = Depends(get_db)
) -> dict:
    try:
        return SubtitleService(db).update_cues(
            subtitle_id, body.cues, style=body.style, preset=body.preset
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/subtitles/{subtitle_id}/overrides")
def add_word_override(
    subtitle_id: str, body: WordOverrideRequest, db: Session = Depends(get_db)
) -> dict:
    try:
        return SubtitleService(db).apply_word_override(
            subtitle_id, body.cue_index, body.override
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/clips/{clip_id}/captions/export")
def export_captions(
    clip_id: str, fmt: str = "srt", db: Session = Depends(get_db)
) -> dict:
    try:
        return SubtitleService(db).export_sidecar(clip_id, fmt=fmt)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
