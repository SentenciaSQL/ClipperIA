"""Transcription, semantic analysis, and highlight endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import require_api_token
from app.infrastructure.database.session import get_db
from app.services.highlight_service import HighlightService
from app.services.semantic_analysis_service import SemanticAnalysisService
from app.services.transcription_service import TranscriptionService

router = APIRouter(tags=["analysis"], dependencies=[Depends(require_api_token)])


class MediaJobRequest(BaseModel):
    media_asset_id: str = Field(min_length=1)
    model_size: str | None = None


class HighlightStatusRequest(BaseModel):
    status: str = Field(min_length=1, max_length=64)


@router.get("/ai/providers")
def ai_providers(db: Session = Depends(get_db)) -> dict:
    return {
        "transcription": {"provider": "faster-whisper", "default": True},
        "vad": {"provider": "silero-vad", "default": True},
        "llm": SemanticAnalysisService(db).provider_status(),
    }


@router.get("/media/{media_asset_id}/transcript")
def get_transcript(media_asset_id: str, db: Session = Depends(get_db)) -> dict:
    row = TranscriptionService(db).get_latest(media_asset_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Transcript not found")
    return row


@router.post("/media/{media_asset_id}/transcribe", status_code=status.HTTP_202_ACCEPTED)
def enqueue_transcription(
    media_asset_id: str,
    model_size: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return TranscriptionService(db).enqueue(media_asset_id, model_size=model_size)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/media/{media_asset_id}/analyze", status_code=status.HTTP_202_ACCEPTED)
def enqueue_semantic_analysis(media_asset_id: str, db: Session = Depends(get_db)) -> dict:
    try:
        return SemanticAnalysisService(db).enqueue(media_asset_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/highlights")
def list_highlights(
    media_asset_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[dict]:
    return HighlightService(db).list_highlights(media_asset_id=media_asset_id)


@router.post(
    "/media/{media_asset_id}/highlights/detect",
    status_code=status.HTTP_202_ACCEPTED,
)
def enqueue_highlight_detection(media_asset_id: str, db: Session = Depends(get_db)) -> dict:
    try:
        return HighlightService(db).enqueue(media_asset_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/highlights/{highlight_id}")
def update_highlight(
    highlight_id: str,
    body: HighlightStatusRequest,
    db: Session = Depends(get_db),
) -> dict:
    try:
        return HighlightService(db).update_status(highlight_id, body.status)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
