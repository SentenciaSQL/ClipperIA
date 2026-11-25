"""Media file storage operations (never mutate originals in-place)."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from app.core.config import Settings
from app.media.paths import media_asset_storage_dir, sanitize_filename


def file_sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def copy_into_library(
    settings: Settings,
    source: Path,
    asset_id: str,
) -> Path:
    """Copy a source video into managed originals storage."""
    dest_dir = media_asset_storage_dir(settings, asset_id)
    dest = dest_dir / sanitize_filename(source.name)
    if dest.exists():
        dest = dest_dir / f"{asset_id}_{sanitize_filename(source.name)}"
    shutil.copy2(source, dest)
    return dest


def delete_asset_files(paths: list[Path | None]) -> None:
    for path in paths:
        if path is None:
            continue
        try:
            if path.is_file():
                path.unlink(missing_ok=True)
            elif path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
        except OSError:
            continue
