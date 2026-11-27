"""Optional OpenAI-compatible cloud LLM adapter."""

from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx

from app.ai.providers.base import LlmProvider
from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class OpenAICompatibleProvider(LlmProvider):
    """
    Cloud LLM via an OpenAI-compatible chat completions API.

    Credentials are read from settings/env only — never hardcoded.
    Works with OpenAI, Azure OpenAI-compatible gateways, Groq, etc.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        self._settings = settings or get_settings()
        self._api_key = (
            api_key
            or getattr(self._settings, "cloud_llm_api_key", None)
            or os.getenv("ACP_CLOUD_LLM_API_KEY")
            or os.getenv("OPENAI_API_KEY")
        )
        self._base_url = (
            base_url
            or getattr(self._settings, "cloud_llm_base_url", None)
            or "https://api.openai.com/v1"
        ).rstrip("/")
        self._model = (
            model
            or getattr(self._settings, "cloud_llm_model", None)
            or "gpt-4o-mini"
        )
        self._timeout = timeout

    @property
    def model_name(self) -> str:
        return self._model

    def available(self) -> bool:
        return bool(self._api_key)

    def analyze_segments(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        if not self._api_key:
            raise RuntimeError(
                "Cloud LLM API key is not configured. Set ACP_CLOUD_LLM_API_KEY."
            )
        model = kwargs.get("model") or self._model
        payload = {
            "model": model,
            "temperature": float(kwargs.get("temperature", 0.2)),
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a video clipping assistant. Always respond with valid JSON."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=self._timeout, headers=headers) as client:
            response = client.post(f"{self._base_url}/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()
        raw = (
            ((data.get("choices") or [{}])[0].get("message") or {}).get("content")
            or "{}"
        )
        parsed = self._parse_json(raw)
        parsed["_provider"] = "cloud_openai_compatible"
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
            return {"raw_text": raw}
