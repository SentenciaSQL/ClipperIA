"""Platform adapter interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LivePlatformAdapter(ABC):
    platform: str

    @abstractmethod
    def get_oauth_authorize_url(self, state: str, redirect_uri: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_stream_status(self, access_token: str, account_id: str | None = None) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_chat_events(
        self,
        access_token: str,
        *,
        channel_id: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    def supports_direct_av_ingest(self) -> bool:
        """Official APIs generally do not expose raw AV for clipping."""
        return False

    def capture_guidance(self) -> dict[str, Any]:
        return {
            "direct_av": False,
            "recommended": "obs_virtual_camera_or_recording",
            "notes": (
                "Use authorized local capture (OBS recording/replay buffer or "
                "desktop capture) because platform metadata/chat APIs do not "
                "provide the audiovisual stream."
            ),
        }
