"""YouTube Live / Data API adapter."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

import httpx

from app.core.config import Settings, get_settings
from app.integrations.base import LivePlatformAdapter


class YouTubeAdapter(LivePlatformAdapter):
    platform = "youtube"
    auth_base = "https://accounts.google.com/o/oauth2/v2/auth"
    token_url = "https://oauth2.googleapis.com/token"
    api_base = "https://www.googleapis.com/youtube/v3"

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    @property
    def client_id(self) -> str | None:
        return getattr(self._settings, "youtube_client_id", None) or None

    @property
    def client_secret(self) -> str | None:
        return getattr(self._settings, "youtube_client_secret", None) or None

    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def get_oauth_authorize_url(self, state: str, redirect_uri: str) -> str:
        if not self.configured():
            raise RuntimeError("YouTube OAuth client is not configured")
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(
                [
                    "https://www.googleapis.com/auth/youtube.readonly",
                    "https://www.googleapis.com/auth/youtube.force-ssl",
                ]
            ),
            "access_type": "offline",
            "include_granted_scopes": "true",
            "state": state,
            "prompt": "consent",
        }
        return f"{self.auth_base}?{urlencode(params)}"

    def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        if not self.configured():
            raise RuntimeError("YouTube OAuth client is not configured")
        with httpx.Client(timeout=30) as client:
            response = client.post(
                self.token_url,
                data={
                    "code": code,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            response.raise_for_status()
            return response.json()

    def get_stream_status(self, access_token: str, account_id: str | None = None) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {access_token}"}
        with httpx.Client(timeout=30, headers=headers) as client:
            channels = client.get(
                f"{self.api_base}/channels",
                params={"part": "snippet,contentDetails", "mine": "true"},
            )
            channels.raise_for_status()
            items = channels.json().get("items") or []
            channel = items[0] if items else {}
            channel_id = channel.get("id") or account_id

            live = client.get(
                f"{self.api_base}/search",
                params={
                    "part": "snippet",
                    "channelId": channel_id,
                    "eventType": "live",
                    "type": "video",
                    "maxResults": 1,
                },
            )
            live.raise_for_status()
            live_items = live.json().get("items") or []
            if not live_items:
                return {
                    "platform": self.platform,
                    "is_live": False,
                    "channel_id": channel_id,
                    "title": channel.get("snippet", {}).get("title"),
                }
            video = live_items[0]
            return {
                "platform": self.platform,
                "is_live": True,
                "channel_id": channel_id,
                "video_id": video.get("id", {}).get("videoId"),
                "title": video.get("snippet", {}).get("title"),
                "thumbnail": (video.get("snippet", {}).get("thumbnails") or {})
                .get("high", {})
                .get("url"),
            }

    def get_chat_events(
        self,
        access_token: str,
        *,
        channel_id: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        # Live chat requires liveChatId from liveBroadcasts; best-effort lookup.
        headers = {"Authorization": f"Bearer {access_token}"}
        with httpx.Client(timeout=30, headers=headers) as client:
            broadcasts = client.get(
                f"{self.api_base}/liveBroadcasts",
                params={
                    "part": "snippet,contentDetails",
                    "broadcastStatus": "active",
                    "mine": "true",
                },
            )
            if broadcasts.status_code != 200:
                return []
            items = broadcasts.json().get("items") or []
            if not items:
                return []
            live_chat_id = (
                items[0].get("snippet", {}).get("liveChatId")
                or items[0].get("contentDetails", {}).get("boundStreamId")
            )
            if not live_chat_id:
                return []
            chat = client.get(
                f"{self.api_base}/liveChat/messages",
                params={
                    "liveChatId": live_chat_id,
                    "part": "snippet,authorDetails",
                    "maxResults": min(limit, 200),
                },
            )
            if chat.status_code != 200:
                return []
            events = []
            for item in chat.json().get("items") or []:
                events.append(
                    {
                        "id": item.get("id"),
                        "author": (item.get("authorDetails") or {}).get("displayName"),
                        "message": (item.get("snippet") or {}).get("displayMessage"),
                        "published_at": (item.get("snippet") or {}).get("publishedAt"),
                        "platform": self.platform,
                    }
                )
            return events
