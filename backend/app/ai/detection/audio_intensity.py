"""Audio intensity / RMS analysis for highlight candidates."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf


def analyze_audio_intensity(
    audio_path: Path,
    *,
    window_seconds: float = 2.0,
) -> list[dict[str, Any]]:
    audio, sr = sf.read(str(audio_path), always_2d=True)
    mono = audio.mean(axis=1).astype(np.float32)
    if mono.size == 0:
        return []
    hop = max(1, int(sr * window_seconds))
    results: list[dict[str, Any]] = []
    for start in range(0, len(mono), hop):
        chunk = mono[start : start + hop]
        if chunk.size == 0:
            continue
        rms = float(np.sqrt(np.mean(np.square(chunk))))
        peak = float(np.max(np.abs(chunk)))
        results.append(
            {
                "start": start / sr,
                "end": (start + chunk.size) / sr,
                "rms": rms,
                "peak": peak,
            }
        )
    if not results:
        return results
    max_rms = max(r["rms"] for r in results) or 1.0
    for row in results:
        row["intensity"] = float(row["rms"] / max_rms)
    return results
