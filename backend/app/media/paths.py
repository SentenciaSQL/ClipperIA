"""Safe path helpers for media storage."""

from __future__ import annotations

import re
from pathlib import Path

from app.core.config import Settings

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(name: str) -> str:
    base = Path(name).name
    cleaned = _SAFE_NAME.sub("_", base).strip("._")
    return cleaned or "media.bin"


def ensure_under(root: Path, candidate: Path) -> Path:
    """Resolve candidate and ensure it stays under root."""
    root_resolved = root.resolve()
    target = candidate.resolve()
    if root_resolved != target and root_resolved not in target.parents:
        raise ValueError("Path escapes storage root")
    return target


def media_asset_storage_dir(settings: Settings, asset_id: str) -> Path:
    path = settings.originals_dir / asset_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def thumbnail_path_for(settings: Settings, asset_id: str) -> Path:
    settings.thumbnails_dir.mkdir(parents=True, exist_ok=True)
    return settings.thumbnails_dir / f"{asset_id}.jpg"
