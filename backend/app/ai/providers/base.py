"""Provider interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class TranscriptionProvider(ABC):
    @abstractmethod
    def transcribe(self, audio_path: str, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError


class LlmProvider(ABC):
    @abstractmethod
    def available(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def analyze_segments(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError
