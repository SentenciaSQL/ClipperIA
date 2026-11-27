"""Optional Demucs audio separation."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


class DemucsSeparator:
    """
    Separates vocals/instrumentals using the demucs CLI when installed.

    This is optional. If demucs is unavailable, callers should surface a clear error.
    """

    def available(self) -> bool:
        return shutil.which("demucs") is not None

    def separate(
        self,
        audio_or_video: Path,
        output_dir: Path,
        *,
        model: str = "htdemucs",
    ) -> dict[str, Any]:
        if not self.available():
            raise RuntimeError(
                "Demucs is not installed. Install with: pip install demucs"
            )
        if not audio_or_video.is_file():
            raise FileNotFoundError(f"Input missing: {audio_or_video}")

        output_dir.mkdir(parents=True, exist_ok=True)
        cmd = [
            "demucs",
            "-n",
            model,
            "-o",
            str(output_dir),
            str(audio_or_video),
        ]
        logger.info("demucs_start", source=str(audio_or_video), model=model)
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=1800)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or "demucs failed")

        # demucs writes output_dir/model/trackname/{vocals,drums,bass,other}.wav
        track_name = audio_or_video.stem
        stem_dir = output_dir / model / track_name
        vocals = stem_dir / "vocals.wav"
        other = stem_dir / "other.wav"
        # instrumental approx = sum of non-vocal stems when present
        instrumental = stem_dir / "no_vocals.wav"
        if not instrumental.exists():
            # keep reference to other as partial instrumental alternative
            instrumental = other if other.exists() else None

        return {
            "model": model,
            "stem_dir": str(stem_dir),
            "vocals": str(vocals) if vocals.exists() else None,
            "instrumental": str(instrumental) if instrumental and instrumental.exists() else None,
            "stems": {
                p.stem: str(p)
                for p in stem_dir.glob("*.wav")
            },
        }
