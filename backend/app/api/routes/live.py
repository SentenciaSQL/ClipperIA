"""Live monitor endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import require_api_token
from app.infrastructure.database.session import get_db
from app.services.live_service import LiveService

router = APIRouter(prefix="/live", tags=["live"], dependencies=[Depends(require_api_token)])


class ConnectionCreateRequest(BaseModel):
    platform: str
    display_name: str = Field(min_length=1)
    external_account_id: str | None = None


class OAuthStartRequest(BaseModel):
    platform: str
    redirect_uri: str


class OAuthCallbackRequest(BaseModel):
    platform: str
    code: str
    redirect_uri: str
    display_name: str | None = None


class CaptureStartRequest(BaseModel):
    connection_id: str
    input_url: str = Field(
        description="Authorized local AV source (OBS device/URL/file). Not a scraped platform CDN URL."
    )
    title: str | None = None
    rolling_seconds: int = Field(default=120, ge=30, le=900)


@router.get("/platforms")
def platforms(db: Session = Depends(get_db)) -> dict:
    return LiveService(db).platform_status()


@router.get("/connections")
def list_connections(db: Session = Depends(get_db)) -> list[dict]:
    return LiveService(db).list_connections()


@router.post("/connections", status_code=status.HTTP_201_CREATED)
def create_connection(body: ConnectionCreateRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return LiveService(db).create_connection(
            platform=body.platform,
            display_name=body.display_name,
            external_account_id=body.external_account_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_connection(connection_id: str, db: Session = Depends(get_db)) -> None:
    try:
        LiveService(db).delete_connection(connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/oauth/start")
def oauth_start(body: OAuthStartRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return LiveService(db).oauth_start(body.platform, body.redirect_uri)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/oauth/callback")
def oauth_callback(body: OAuthCallbackRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return LiveService(db).oauth_callback(
            body.platform,
            code=body.code,
            redirect_uri=body.redirect_uri,
            display_name=body.display_name,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/connections/{connection_id}/refresh")
def refresh_status(connection_id: str, db: Session = Depends(get_db)) -> dict:
    try:
        return LiveService(db).refresh_status(connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/connections/{connection_id}/chat")
def get_chat(
    connection_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[dict]:
    try:
        return LiveService(db).get_chat(connection_id, limit=limit)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/sessions")
def list_sessions(db: Session = Depends(get_db)) -> list[dict]:
    return LiveService(db).list_sessions()


@router.post("/sessions/capture", status_code=status.HTTP_201_CREATED)
def start_capture(body: CaptureStartRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return LiveService(db).start_local_capture_session(
            body.connection_id,
            input_url=body.input_url,
            title=body.title,
            rolling_seconds=body.rolling_seconds,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/stop")
def stop_session(session_id: str, db: Session = Depends(get_db)) -> dict:
    try:
        return LiveService(db).stop_session(session_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/highlights", status_code=status.HTTP_202_ACCEPTED)
def live_highlights(session_id: str, db: Session = Depends(get_db)) -> dict:
    try:
        return LiveService(db).enqueue_live_highlight_pass(session_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
