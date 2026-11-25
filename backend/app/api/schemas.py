"""Pydantic request/response schemas for Phase 1 APIs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    app_name: str
    version: str
    environment: str


class AuthBootstrapResponse(BaseModel):
    api_token: str
    base_url: str
    websocket_url: str


class SettingUpsertRequest(BaseModel):
    key: str = Field(min_length=1, max_length=128)
    value: Any
    description: str | None = None


class SettingResponse(BaseModel):
    id: str
    key: str
    value: Any
    description: str | None = None
    updated_at: str | None = None


class RuntimeConfigResponse(BaseModel):
    app_name: str
    app_version: str
    environment: str
    host: str
    port: int
    data_root: str
    max_concurrent_jobs: int
    max_gpu_inference_jobs: int
    whisper_model_size: str | None = None
    ollama_base_url: str | None = None
    ollama_model: str | None = None
    ai_provider: str | None = None
    highlight_weights: dict[str, Any] | None = None
    persisted: dict[str, Any]


class WebSocketEvent(BaseModel):
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)
