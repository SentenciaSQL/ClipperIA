"""Storage usage reporting and cache cleanup."""

from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Any

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class StorageService:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def usage(self) -> dict[str, Any]:
        buckets = {
            "originals": self._settings.originals_dir,
            "recordings": self._settings.recordings_dir,
            "cache": self._settings.cache_dir,
            "clips": self._settings.clips_dir,
            "exports": self._settings.exports_dir,
            "subtitles": self._settings.subtitles_dir,
            "thumbnails": self._settings.thumbnails_dir,
            "models": self._settings.models_dir,
            "logs": self._settings.logs_dir,
            "database": self._settings.database_dir,
        }
        details = []
        total = 0
        for name, path in buckets.items():
            size = self._dir_size(path)
            total += size
            details.append(
                {
                    "name": name,
                    "path": str(path),
                    "size_mb": round(size / (1024 * 1024), 2),
                    "exists": path.exists(),
                }
            )
        disk = shutil.disk_usage(self._settings.data_root)
        return {
            "data_root": str(self._settings.data_root),
            "total_used_mb": round(total / (1024 * 1024), 2),
            "cache_max_mb": self._settings.storage_cache_max_mb,
            "disk_total_mb": round(disk.total / (1024 * 1024), 2),
            "disk_free_mb": round(disk.free / (1024 * 1024), 2),
            "buckets": details,
        }

    def cleanup_cache(
        self,
        *,
        older_than_hours: float = 72,
        max_mb: float | None = None,
    ) -> dict[str, Any]:
        cache = self._settings.cache_dir
        if not cache.exists():
            return {"deleted_files": 0, "freed_mb": 0}
        cutoff = time.time() - older_than_hours * 3600
        deleted = 0
        freed = 0
        files = sorted(
            (p for p in cache.rglob("*") if p.is_file()),
            key=lambda p: p.stat().st_mtime,
        )
        for path in files:
            try:
                stat = path.stat()
            except OSError:
                continue
            over_age = stat.st_mtime < cutoff
            over_budget = False
            if max_mb is not None:
                current = self._dir_size(cache) / (1024 * 1024)
                over_budget = current > max_mb
            if not (over_age or over_budget):
                continue
            try:
                size = stat.st_size
                path.unlink(missing_ok=True)
                deleted += 1
                freed += size
            except OSError as exc:
                logger.warning("cache_delete_failed", path=str(path), error=str(exc))
        # Remove empty dirs
        for path in sorted(cache.rglob("*"), reverse=True):
            if path.is_dir():
                try:
                    path.rmdir()
                except OSError:
                    pass
        return {
            "deleted_files": deleted,
            "freed_mb": round(freed / (1024 * 1024), 2),
            "usage": self.usage(),
        }

    def optimize_if_needed(self) -> dict[str, Any] | None:
        if not self._settings.storage_auto_cleanup:
            return None
        usage = self.usage()
        cache_bucket = next((b for b in usage["buckets"] if b["name"] == "cache"), None)
        if cache_bucket and cache_bucket["size_mb"] > self._settings.storage_cache_max_mb:
            return self.cleanup_cache(max_mb=float(self._settings.storage_cache_max_mb))
        return None

    @staticmethod
    def _dir_size(path: Path) -> int:
        if not path.exists():
            return 0
        total = 0
        for child in path.rglob("*"):
            if child.is_file():
                try:
                    total += child.stat().st_size
                except OSError:
                    continue
        return total
