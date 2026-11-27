"""Local API authentication helpers."""

from __future__ import annotations

from fastapi import Header, HTTPException, Query, status

from app.core.config import get_settings


async def require_api_token(
    x_api_token: str | None = Header(default=None, alias="X-API-Token"),
    token: str | None = Query(
        default=None,
        description="Optional token for browser media URLs (same value as X-API-Token).",
    ),
) -> str:
    """Validate the per-session local API token (header or query)."""
    settings = get_settings()
    provided = x_api_token or token
    if not provided or provided != settings.api_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API token",
        )
    return provided
