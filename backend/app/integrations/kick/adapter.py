"""Kick OAuth / API adapter (documented public endpoints)."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

import httpx

from app.core.config import Settings, get_settings
from app.integrations.base import LivePlatformAdapter


class KickAdapter(LivePlatformAdapter):
    """
    Kick integration via Kick's developer OAuth/API when credentials are provided.

    Kick's public API surface evolves; this adapter uses configurable base URLs
    and fails clearly when endpoints/credentials are unavailable.
    """

    platform = "kick"

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self.auth_base = getattr(self._settings, "kick_auth_base", None) or "https://id.kick.com/oauth/authorize"
        self.token_url = getattr(self._settings, "kick_token_url", None) or "https://id.kick.com/oauth/token"
        self.api_base = getattr(self._settings, "kick_api_base", None) or "https://api.kick.com/public/v1"

    @property
    def client_id(self) -> str | None:
        return getattr(self._settings, "kick_client_id", None) or None

    @property
    def client_secret(self) -> str | None:
        return getattr(self._settings, "kick_client_secret", None) or None

    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def get_oauth_authorize_url(self, state: str, redirect_uri: str) -> str:
        if not self.configured():
            raise RuntimeError("Kick OAuth client is not configured")
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "user:read channel:read chat:read",
            "state": state,
        }
        return f"{self.auth_base}?{urlencode(params)}"

    def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        if not self.configured():
            raise RuntimeError("Kick OAuth client is not configured")
        with httpx.Client(timeout=30) as client:
            response = client.post(
                self.token_url,
                data={
                    "grant_type": "authorization_code",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": redirect_uri,
                    "code": code,
                },
            )
            response.raise_for_status()
            return response.json()

    def get_stream_status(self, access_token: str, account_id: str | None = None) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {access_token}"}
        with httpx.Client(timeout=30, headers=headers) as client:
            # Best-effort against Kick public API; surface upstream errors clearly.
            response = client.get(f"{self.api_base}/channels", params={"slug": account_id} if account_id else None)
            if response.status_code >= 400:
                return {
                    "platform": self.platform,
                    "is_live": False,
                    "error": response.text,
                    "configured": True,
                }
            data = response.json()
            channel = (data.get("data") or [data])[0] if isinstance(data, dict) else {}
            return {
                "platform": self.platform,
                "is_live": bool(channel.get("stream") or channel.get("is_live")),
                "title": channel.get("session_title") or channel.get("title"),
                "raw": channel,
            }

    def get_chat_events(
        self,
        access_token: str,
        *,
        channel_id: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        return []

    def capture_guidance(self) -> dict[str, Any]:
        base = super().capture_guidance()
        base["notes"] = (
            "Kick does not provide a supported raw AV download API for arbitrary "
            "live streams. Use OBS local recording/replay buffer for authorized capture."
        )
        return base
