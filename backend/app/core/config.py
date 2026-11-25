"""Centralized application configuration."""

from __future__ import annotations

import secrets
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def default_data_root() -> Path:
    """Return the default local data directory for the current OS."""
    home = Path.home()
    documents = home / "Documents"
    if documents.is_dir():
        return documents / "AIClippingPlatform"
    return home / "AIClippingPlatform"


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="ACP_",
        extra="ignore",
    )

    app_name: str = "AI Clipping Platform"
    app_version: str = "0.7.0"
    environment: str = "development"
    debug: bool = False

    # Local API — bind to loopback only by default
    host: str = "127.0.0.1"
    port: int = 8765
    api_prefix: str = "/api/v1"

    # Session token for local frontend ↔ backend auth
    api_token: str = Field(default_factory=lambda: secrets.token_urlsafe(32))

    # Storage
    data_root: Path = Field(default_factory=default_data_root)
    database_filename: str = "ai_clipping.db"

    # Logging
    log_level: str = "INFO"
    log_json: bool = False

    # Resource defaults / concurrency
    max_concurrent_jobs: int = 2
    max_gpu_inference_jobs: int = 1

    # AI defaults (local-first)
    whisper_model_size: str = "base"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3:8b"
    ai_provider: str = "local"

    # Highlight scoring weights (must sum conceptually to 1.0)
    score_audio_intensity: float = 0.20
    score_voice_emotion: float = 0.20
    score_semantic: float = 0.25
    score_chat_activity: float = 0.15
    score_visual_changes: float = 0.10
    score_narrative_quality: float = 0.10

    # Clip defaults
    default_clip_duration: float = 30.0
    default_aspect_ratio: str = "9:16"

    # Platform OAuth (optional; never hardcode secrets)
    youtube_client_id: str | None = None
    youtube_client_secret: str | None = None
    twitch_client_id: str | None = None
    twitch_client_secret: str | None = None
    kick_client_id: str | None = None
    kick_client_secret: str | None = None
    kick_auth_base: str | None = None
    kick_token_url: str | None = None
    kick_api_base: str | None = None

    @property
    def database_dir(self) -> Path:
        return self.data_root / "database"

    @property
    def database_url(self) -> str:
        db_path = self.database_dir / self.database_filename
        return f"sqlite:///{db_path.as_posix()}"

    @property
    def media_dir(self) -> Path:
        return self.data_root / "media"

    @property
    def originals_dir(self) -> Path:
        return self.media_dir / "originals"

    @property
    def recordings_dir(self) -> Path:
        return self.media_dir / "recordings"

    @property
    def cache_dir(self) -> Path:
        return self.media_dir / "cache"

    @property
    def projects_dir(self) -> Path:
        return self.data_root / "projects"

    @property
    def clips_dir(self) -> Path:
        return self.data_root / "clips"

    @property
    def exports_dir(self) -> Path:
        return self.data_root / "exports"

    @property
    def subtitles_dir(self) -> Path:
        return self.data_root / "subtitles"

    @property
    def thumbnails_dir(self) -> Path:
        return self.data_root / "thumbnails"

    @property
    def models_dir(self) -> Path:
        return self.data_root / "models"

    @property
    def logs_dir(self) -> Path:
        return self.data_root / "logs"

    def storage_directories(self) -> list[Path]:
        return [
            self.database_dir,
            self.originals_dir,
            self.recordings_dir,
            self.cache_dir,
            self.projects_dir,
            self.clips_dir,
            self.exports_dir,
            self.subtitles_dir,
            self.thumbnails_dir,
            self.models_dir,
            self.logs_dir,
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
