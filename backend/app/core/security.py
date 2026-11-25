"""Local API authentication helpers."""

from __future__ import annotations

from fastapi import Header, HTTPException, status

from app.core.config import get_settings


async def require_api_token(
    x_api_token: str | None = Header(default=None, alias="X-API-Token"),
) -> str:
    """Validate the per-session local API token."""
    settings = get_settings()
    if not x_api_token or x_api_token != settings.api_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API token",
        )
    return x_api_token
