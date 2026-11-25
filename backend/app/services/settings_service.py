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
            "persisted": persisted,
        }

    def upsert(self, key: str, value: Any, description: str | None = None) -> dict[str, Any]:
        item = self._repo.upsert(key=key, value=value, description=description)
        return {
            "id": item.id,
            "key": item.key,
            "value": item.value_json,
            "description": item.description,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        }
