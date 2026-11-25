"""faster-whisper transcription provider."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.ai.providers.base import TranscriptionProvider
from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class FasterWhisperProvider(TranscriptionProvider):
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._model = None
        self._model_size: str | None = None
        self._device: str | None = None

    def _resolve_device(self) -> tuple[str, str]:
        # CUDA when available; otherwise CPU + int8
        try:
            import torch

            if torch.cuda.is_available():
                return "cuda", "float16"
        except Exception:  # noqa: BLE001
            pass
        return "cpu", "int8"

    def _load(self, model_size: str) -> None:
        if self._model is not None and self._model_size == model_size:
            return
        from faster_whisper import WhisperModel

        device, compute_type = self._resolve_device()
        download_root = str(self._settings.models_dir / "whisper")
        Path(download_root).mkdir(parents=True, exist_ok=True)
        logger.info(
            "loading_whisper_model",
            model_size=model_size,
            device=device,
            compute_type=compute_type,
        )
        self._model = WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type,
            download_root=download_root,
        )
        self._model_size = model_size
        self._device = device

    def transcribe(
        self,
        audio_path: str,
        *,
        model_size: str = "base",
        language: str | None = None,
        vad_filter: bool = True,
        **kwargs: Any,
    ) -> dict[str, Any]:
        self._load(model_size)
        assert self._model is not None
        segments_iter, info = self._model.transcribe(
            audio_path,
            language=language,
            word_timestamps=True,
            vad_filter=vad_filter,
            beam_size=int(kwargs.get("beam_size", 5)),
        )
        segments: list[dict[str, Any]] = []
        full_parts: list[str] = []
        for seg in segments_iter:
            words = []
            if seg.words:
                words = [
                    {
                        "start": float(w.start),
                        "end": float(w.end),
                        "word": w.word,
                        "probability": float(w.probability) if w.probability is not None else None,
                    }
                    for w in seg.words
                ]
            item = {
                "id": seg.id,
                "start": float(seg.start),
                "end": float(seg.end),
                "text": seg.text.strip(),
                "avg_logprob": float(seg.avg_logprob) if seg.avg_logprob is not None else None,
                "no_speech_prob": float(seg.no_speech_prob)
                if seg.no_speech_prob is not None
                else None,
                "words": words,
            }
            segments.append(item)
            if item["text"]:
                full_parts.append(item["text"])

        return {
            "language": info.language,
            "language_probability": float(info.language_probability),
            "duration": float(info.duration) if info.duration is not None else None,
            "full_text": " ".join(full_parts).strip(),
            "segments": segments,
            "model_name": f"faster-whisper-{model_size}",
            "device": self._device,
        }
