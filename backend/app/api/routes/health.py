"""Health and bootstrap endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.schemas import AuthBootstrapResponse, HealthResponse
from app.core.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )


@router.get("/auth/bootstrap", response_model=AuthBootstrapResponse)
def auth_bootstrap() -> AuthBootstrapResponse:
    """
    Return the local session API token for the desktop client.

    Bound to localhost only. In production packaging this endpoint can be
    further restricted to the launcher process.
    """
    settings = get_settings()
    base = f"http://{settings.host}:{settings.port}{settings.api_prefix}"
    ws = f"ws://{settings.host}:{settings.port}{settings.api_prefix}/ws"
    return AuthBootstrapResponse(
        api_token=settings.api_token,
        base_url=base,
        websocket_url=ws,
    )
