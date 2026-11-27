"""Local model inventory and Whisper download helpers."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

WHISPER_SIZES = ("tiny", "base", "small", "medium", "large-v3")


class ModelManagementService:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def inventory(self) -> dict[str, Any]:
        whisper_root = self._settings.models_dir / "whisper"
        whisper_root.mkdir(parents=True, exist_ok=True)
        installed = []
        for path in sorted(whisper_root.iterdir()) if whisper_root.exists() else []:
            if path.is_dir() or path.suffix in {".bin", ".pt", ".gguf"}:
                installed.append(
                    {
                        "name": path.name,
                        "path": str(path),
                        "size_mb": round(self._path_size(path) / (1024 * 1024), 2),
                    }
                )
        return {
            "models_dir": str(self._settings.models_dir),
            "whisper": {
                "download_root": str(whisper_root),
                "available_sizes": list(WHISPER_SIZES),
                "default_size": self._settings.whisper_model_size,
                "installed": installed,
            },
            "ollama": {
                "base_url": self._settings.ollama_base_url,
                "configured_model": self._settings.ollama_model,
                "note": "Pull models with: ollama pull <model>",
            },
        }

    def ensure_whisper(self, model_size: str = "base") -> dict[str, Any]:
        if model_size not in WHISPER_SIZES:
            raise ValueError(f"Unsupported Whisper size '{model_size}'")
        from faster_whisper import WhisperModel

        download_root = str(self._settings.models_dir / "whisper")
        Path(download_root).mkdir(parents=True, exist_ok=True)
        logger.info("ensuring_whisper_model", model_size=model_size)
        # Instantiating downloads weights into download_root when missing
        WhisperModel(model_size, device="cpu", compute_type="int8", download_root=download_root)
        return {
            "status": "ready",
            "model_size": model_size,
            "download_root": download_root,
            "inventory": self.inventory(),
        }

    def delete_whisper_cache(self, name: str | None = None) -> dict[str, Any]:
        root = self._settings.models_dir / "whisper"
        if not root.exists():
            return {"deleted": [], "freed_mb": 0}
        deleted: list[str] = []
        freed = 0
        targets = [root / name] if name else list(root.iterdir())
        for path in targets:
            if not path.exists() or not str(path.resolve()).startswith(str(root.resolve())):
                continue
            size = self._path_size(path)
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            else:
                path.unlink(missing_ok=True)
            deleted.append(str(path))
            freed += size
        return {"deleted": deleted, "freed_mb": round(freed / (1024 * 1024), 2)}

    @staticmethod
    def _path_size(path: Path) -> int:
        if path.is_file():
            return path.stat().st_size
        total = 0
        for child in path.rglob("*"):
            if child.is_file():
                total += child.stat().st_size
        return total
