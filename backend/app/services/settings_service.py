"""Application settings service."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.repositories.settings_repository import SettingsRepository


class SettingsService:
    def __init__(self, db: Session, app_settings: Settings | None = None) -> None:
        self._repo = SettingsRepository(db)
        self._app = app_settings or get_settings()

    def get_runtime_config(self) -> dict[str, Any]:
        persisted = {
            item.key: item.value_json
            for item in self._repo.list_all()
        }
        return {
            "app_name": self._app.app_name,
            "app_version": self._app.app_version,
            "environment": self._app.environment,
            "host": self._app.host,
            "port": self._app.port,
            "data_root": str(self._app.data_root),
            "max_concurrent_jobs": self._app.max_concurrent_jobs,
            "max_gpu_inference_jobs": self._app.max_gpu_inference_jobs,
            "whisper_model_size": self._app.whisper_model_size,
            "ollama_base_url": self._app.ollama_base_url,
            "ollama_model": self._app.ollama_model,
            "ai_provider": self._app.ai_provider,
            "cloud_llm_base_url": self._app.cloud_llm_base_url,
            "cloud_llm_model": self._app.cloud_llm_model,
            "cloud_llm_configured": bool(self._app.cloud_llm_api_key),
            "storage_cache_max_mb": self._app.storage_cache_max_mb,
            "job_recovery_enabled": self._app.job_recovery_enabled,
            "highlight_weights": {
                "audio_intensity": self._app.score_audio_intensity,
                "voice_emotion": self._app.score_voice_emotion,
                "semantic": self._app.score_semantic,
                "chat_activity": self._app.score_chat_activity,
                "visual_changes": self._app.score_visual_changes,
                "narrative_quality": self._app.score_narrative_quality,
            },
            "persisted": persisted,
        }

    def get(self, key: str) -> Any | None:
        item = self._repo.get(key)
        return None if item is None else item.value_json

    def upsert(self, key: str, value: Any, description: str | None = None) -> dict[str, Any]:
        item = self._repo.upsert(key=key, value=value, description=description)
        return {
            "id": item.id,
            "key": item.key,
            "value": item.value_json,
            "description": item.description,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        }
