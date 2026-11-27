"""Twitch Helix adapter."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

import httpx

from app.core.config import Settings, get_settings
from app.integrations.base import LivePlatformAdapter


class TwitchAdapter(LivePlatformAdapter):
    platform = "twitch"
    auth_base = "https://id.twitch.tv/oauth2/authorize"
    token_url = "https://id.twitch.tv/oauth2/token"
    api_base = "https://api.twitch.tv/helix"

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    @property
    def client_id(self) -> str | None:
        return getattr(self._settings, "twitch_client_id", None) or None

    @property
    def client_secret(self) -> str | None:
        return getattr(self._settings, "twitch_client_secret", None) or None

    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def get_oauth_authorize_url(self, state: str, redirect_uri: str) -> str:
        if not self.configured():
            raise RuntimeError("Twitch OAuth client is not configured")
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "user:read:email chat:read channel:read:subscriptions",
            "state": state,
        }
        return f"{self.auth_base}?{urlencode(params)}"

    def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        if not self.configured():
            raise RuntimeError("Twitch OAuth client is not configured")
        with httpx.Client(timeout=30) as client:
            response = client.post(
                self.token_url,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                },
            )
            response.raise_for_status()
            return response.json()

    def _headers(self, access_token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {access_token}",
            "Client-Id": str(self.client_id),
        }

    def get_stream_status(self, access_token: str, account_id: str | None = None) -> dict[str, Any]:
        headers = self._headers(access_token)
        with httpx.Client(timeout=30, headers=headers) as client:
            user = client.get(f"{self.api_base}/users")
            user.raise_for_status()
            users = user.json().get("data") or []
            me = users[0] if users else {}
            user_id = account_id or me.get("id")
            streams = client.get(
                f"{self.api_base}/streams",
                params={"user_id": user_id},
            )
            streams.raise_for_status()
            data = streams.json().get("data") or []
            if not data:
                return {
                    "platform": self.platform,
                    "is_live": False,
                    "user_id": user_id,
                    "login": me.get("login"),
                    "display_name": me.get("display_name"),
                }
            stream = data[0]
            return {
                "platform": self.platform,
                "is_live": True,
                "user_id": user_id,
                "login": me.get("login"),
                "display_name": me.get("display_name"),
                "title": stream.get("title"),
                "game_name": stream.get("game_name"),
                "viewer_count": stream.get("viewer_count"),
                "started_at": stream.get("started_at"),
                "thumbnail_url": stream.get("thumbnail_url"),
            }

    def get_chat_events(
        self,
        access_token: str,
        *,
        channel_id: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        # Helix chat message history requires EventSub / IRC for realtime.
        # Document limitation and return empty with guidance.
        return []

    def capture_guidance(self) -> dict[str, Any]:
        base = super().capture_guidance()
        base["chat"] = (
            "Use Twitch IRC/EventSub for realtime chat. Helix alone does not "
            "expose a historical chat dump for arbitrary live sessions."
        )
        return base
