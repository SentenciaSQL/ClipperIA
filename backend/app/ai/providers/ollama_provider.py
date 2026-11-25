"""Ollama LLM provider (local Qwen3 by default)."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.ai.providers.base import LlmProvider
from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class OllamaProvider(LlmProvider):
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        self._settings = settings or get_settings()
        self._base_url = (base_url or getattr(self._settings, "ollama_base_url", None) or "http://127.0.0.1:11434").rstrip("/")
        self._model = model or getattr(self._settings, "ollama_model", None) or "qwen3:8b"
        self._timeout = timeout

    @property
    def model_name(self) -> str:
        return self._model

    def available(self) -> bool:
        try:
            with httpx.Client(timeout=3.0) as client:
                response = client.get(f"{self._base_url}/api/tags")
                if response.status_code != 200:
                    return False
                models = response.json().get("models") or []
                names = {m.get("name") for m in models}
                # Accept exact or tagless match
                if self._model in names:
                    return True
                base = self._model.split(":")[0]
                return any(isinstance(n, str) and n.startswith(base) for n in names)
        except Exception:  # noqa: BLE001
            return False

    def list_models(self) -> list[str]:
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{self._base_url}/api/tags")
                response.raise_for_status()
                return [m.get("name") for m in (response.json().get("models") or []) if m.get("name")]
        except Exception as exc:  # noqa: BLE001
            logger.warning("ollama_list_models_failed", error=str(exc))
            return []

    def analyze_segments(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        model = kwargs.get("model") or self._model
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": float(kwargs.get("temperature", 0.2)),
            },
        }
        with httpx.Client(timeout=self._timeout) as client:
            response = client.post(f"{self._base_url}/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()
        raw = data.get("response") or "{}"
        parsed = self._parse_json(raw)
        parsed["_provider"] = "ollama"
        parsed["_model"] = model
        return parsed

    @staticmethod
    def _parse_json(raw: str) -> dict[str, Any]:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
            return {"raw_text": raw, "moments": []}
