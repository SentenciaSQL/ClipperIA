"""Local storage directory management."""

from __future__ import annotations

from pathlib import Path

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def ensure_storage_layout(settings: Settings) -> list[Path]:
    """Create the default storage directory tree if missing."""
    created: list[Path] = []
    for path in settings.storage_directories():
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            created.append(path)
            logger.info("storage_directory_created", path=str(path))
    return created
