"""Repository for application settings persistence."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.database.models import AppSetting


class SettingsRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get(self, key: str) -> AppSetting | None:
        stmt = select(AppSetting).where(AppSetting.key == key)
        return self._db.scalar(stmt)

    def list_all(self) -> list[AppSetting]:
        stmt = select(AppSetting).order_by(AppSetting.key)
        return list(self._db.scalars(stmt).all())

    def upsert(self, key: str, value: Any, description: str | None = None) -> AppSetting:
        existing = self.get(key)
        if existing is None:
            existing = AppSetting(key=key, value_json=value, description=description)
            self._db.add(existing)
        else:
            existing.value_json = value
            if description is not None:
                existing.description = description
        self._db.commit()
        self._db.refresh(existing)
        return existing
