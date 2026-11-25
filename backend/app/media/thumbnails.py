"""Thumbnail generation via FFmpeg."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger(__name__)


class ThumbnailError(Exception):
    pass


class ThumbnailService:
    def generate(
        self,
        source: Path,
        destination: Path,
        *,
        at_seconds: float = 1.0,
        width: int = 480,
    ) -> Path:
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg is None:
            raise ThumbnailError("ffmpeg not found on PATH")
        if not source.is_file():
            raise ThumbnailError(f"Source not found: {source}")

        destination.parent.mkdir(parents=True, exist_ok=True)
        seek = max(0.0, at_seconds)
        cmd = [
            ffmpeg,
            "-y",
            "-ss",
            f"{seek:.3f}",
            "-i",
            str(source),
            "-frames:v",
            "1",
            "-vf",
            f"scale={width}:-2",
            "-q:v",
            "3",
            str(destination),
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=60,
            )
        except (OSError, subprocess.SubprocessError, TimeoutError) as exc:
            raise ThumbnailError(f"thumbnail generation failed: {exc}") from exc

        if proc.returncode != 0 or not destination.is_file():
            # Retry at t=0 for very short clips
            if seek > 0:
                return self.generate(source, destination, at_seconds=0.0, width=width)
            raise ThumbnailError(proc.stderr.strip() or "thumbnail generation failed")

        logger.info("thumbnail_created", path=str(destination))
        return destination
