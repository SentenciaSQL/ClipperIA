"""AI provider registry and selection."""

from __future__ import annotations

from typing import Any

from app.ai.providers.base import LlmProvider
from app.ai.providers.cloud_openai import OpenAICompatibleProvider
from app.ai.providers.ollama_provider import OllamaProvider
from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class ProviderRegistry:
    """Resolves local-first LLM providers with optional cloud fallback."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._ollama = OllamaProvider(self._settings)
        self._cloud = OpenAICompatibleProvider(self._settings)

    def status(self) -> dict[str, Any]:
        return {
            "default_mode": self._settings.ai_provider,
            "prefer_local": self._settings.ai_provider in {"local", "auto"},
            "local": {
                "id": "ollama",
                "available": self._ollama.available(),
                "endpoint": self._settings.ollama_base_url,
                "model": self._settings.ollama_model,
                "models": self._ollama.list_models(),
            },
            "cloud": {
                "id": "openai_compatible",
                "available": self._cloud.available(),
                "endpoint": getattr(
                    self._settings, "cloud_llm_base_url", "https://api.openai.com/v1"
                ),
                "model": getattr(self._settings, "cloud_llm_model", "gpt-4o-mini"),
                "api_key_configured": bool(
                    getattr(self._settings, "cloud_llm_api_key", None)
                ),
            },
            "transcription": {
                "id": "faster-whisper",
                "default_model": self._settings.whisper_model_size,
            },
        }

    def get_llm(self, prefer: str | None = None) -> tuple[str, LlmProvider]:
        mode = (prefer or self._settings.ai_provider or "local").lower()
        if mode == "cloud":
            if not self._cloud.available():
                raise RuntimeError("Cloud LLM requested but API key is not configured")
            return "cloud", self._cloud
        if mode == "local":
            if self._ollama.available():
                return "local", self._ollama
            raise RuntimeError("Local Ollama provider is unavailable")
        # auto: local first, then cloud
        if self._ollama.available():
            return "local", self._ollama
        if self._cloud.available():
            logger.info("falling_back_to_cloud_llm")
            return "cloud", self._cloud
        raise RuntimeError("No LLM provider available (Ollama offline and no cloud key)")
