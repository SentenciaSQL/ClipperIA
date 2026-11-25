"""Audio extraction helpers."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger(__name__)


class AudioExtractionError(Exception):
    pass


def extract_wav_mono_16k(source: Path, destination: Path) -> Path:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise AudioExtractionError("ffmpeg not found on PATH")
    destination.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(source),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(destination),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=300)
    if proc.returncode != 0 or not destination.is_file():
        raise AudioExtractionError(proc.stderr.strip() or "audio extraction failed")
    logger.info("audio_extracted", path=str(destination))
    return destination
