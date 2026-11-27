"""Advanced processing profiles."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.repositories.settings_repository import SettingsRepository

DEFAULT_PROFILES: dict[str, dict[str, Any]] = {
    "balanced": {
        "label": "Balanced",
        "whisper_model_size": "base",
        "ai_provider": "local",
        "max_duration": 30,
        "aspect_ratio": "9:16",
        "export_preset": "tiktok",
        "generate_captions": True,
        "smart_reframe": True,
        "generate_metadata": True,
        "clip_limit": 5,
    },
    "fast": {
        "label": "Fast draft",
        "whisper_model_size": "tiny",
        "ai_provider": "local",
        "max_duration": 20,
        "aspect_ratio": "9:16",
        "export_preset": "tiktok",
        "generate_captions": False,
        "smart_reframe": False,
        "generate_metadata": False,
        "clip_limit": 3,
    },
    "quality": {
        "label": "Quality",
        "whisper_model_size": "small",
        "ai_provider": "auto",
        "max_duration": 45,
        "aspect_ratio": "9:16",
        "export_preset": "youtube_shorts",
        "generate_captions": True,
        "smart_reframe": True,
        "generate_metadata": True,
        "clip_limit": 8,
    },
    "cloud_assist": {
        "label": "Cloud assist",
        "whisper_model_size": "base",
        "ai_provider": "cloud",
        "max_duration": 30,
        "aspect_ratio": "9:16",
        "export_preset": "instagram_reels",
        "generate_captions": True,
        "smart_reframe": True,
        "generate_metadata": True,
        "clip_limit": 5,
    },
}


class ProfileService:
    def __init__(self, db: Session, settings: Settings | None = None) -> None:
        self._repo = SettingsRepository(db)
        self._settings = settings or get_settings()

    def list_profiles(self) -> dict[str, Any]:
        custom = self._repo.get("processing_profiles")
        merged = deepcopy(DEFAULT_PROFILES)
        if custom and isinstance(custom.value_json, dict):
            merged.update(custom.value_json)
        active = self._repo.get("active_processing_profile")
        return {
            "active": (active.value_json if active else "balanced"),
            "profiles": merged,
        }

    def upsert_profile(self, profile_id: str, profile: dict[str, Any]) -> dict[str, Any]:
        current = self.list_profiles()["profiles"]
        current[profile_id] = profile
        self._repo.upsert("processing_profiles", current, "Custom processing profiles")
        return {"id": profile_id, "profile": profile}

    def set_active(self, profile_id: str) -> dict[str, Any]:
        profiles = self.list_profiles()["profiles"]
        if profile_id not in profiles:
            raise LookupError(f"Unknown profile '{profile_id}'")
        self._repo.upsert("active_processing_profile", profile_id, "Active processing profile")
        return {"active": profile_id, "profile": profiles[profile_id]}

    def get_active(self) -> dict[str, Any]:
        data = self.list_profiles()
        active = data["active"] if isinstance(data["active"], str) else "balanced"
        profile = data["profiles"].get(active) or DEFAULT_PROFILES["balanced"]
        return {"id": active, "profile": profile}
