"""Silero VAD speech-segment detection."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

from app.core.logging import get_logger

logger = get_logger(__name__)


class SileroVadService:
    """Voice activity detection using Silero via torch.hub."""

    def __init__(self) -> None:
        self._model = None
        self._utils = None
        self._sample_rate = 16000

    def _load(self) -> None:
        if self._model is not None:
            return
        import torch

        logger.info("loading_silero_vad")
        model, utils = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            trust_repo=True,
        )
        self._model = model
        self._utils = utils

    def _load_mono_16k(self, audio_path: str | Path):
        import torch

        audio, sr = sf.read(str(audio_path), always_2d=True)
        mono = audio.mean(axis=1).astype(np.float32)
        if sr != self._sample_rate:
            duration = len(mono) / float(sr)
            target_len = max(1, int(duration * self._sample_rate))
            x_old = np.linspace(0.0, 1.0, num=len(mono), endpoint=False)
            x_new = np.linspace(0.0, 1.0, num=target_len, endpoint=False)
            mono = np.interp(x_new, x_old, mono).astype(np.float32)
        return torch.from_numpy(mono)

    def detect_speech_segments(
        self,
        audio_path: str | Path,
        *,
        threshold: float = 0.5,
        min_speech_ms: int = 250,
        min_silence_ms: int = 100,
    ) -> list[dict[str, Any]]:
        self._load()
        assert self._model is not None and self._utils is not None

        wav = self._load_mono_16k(audio_path)
        get_speech_timestamps = self._utils[0]
        timestamps = get_speech_timestamps(
            wav,
            self._model,
            sampling_rate=self._sample_rate,
            threshold=threshold,
            min_speech_duration_ms=min_speech_ms,
            min_silence_duration_ms=min_silence_ms,
        )
        segments = []
        for ts in timestamps:
            start = float(ts["start"]) / self._sample_rate
            end = float(ts["end"]) / self._sample_rate
            segments.append({"start": start, "end": end, "duration": end - start})
        logger.info("vad_segments_detected", count=len(segments), path=str(audio_path))
        return segments

    def speech_ratio(self, segments: list[dict[str, Any]], total_duration: float) -> float:
        if total_duration <= 0:
            return 0.0
        spoken = sum(float(s["duration"]) for s in segments)
        return float(np.clip(spoken / total_duration, 0.0, 1.0))
