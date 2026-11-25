"""SQLAlchemy ORM models for the AI Clipping Platform."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class ProcessingStatus(str, enum.Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(64), default="active", nullable=False)

    media_assets: Mapped[list[MediaAsset]] = relationship(back_populates="project")
    clips: Mapped[list[Clip]] = relationship(back_populates="project")
    jobs: Mapped[list[ProcessingJob]] = relationship(back_populates="project")


class MediaAsset(Base, TimestampMixin):
    __tablename__ = "media_assets"
    __table_args__ = (
        Index("ix_media_assets_project_created", "project_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    media_type: Mapped[str] = mapped_column(String(64), default="video", nullable=False)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    frame_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    video_codec: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    audio_codec: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    thumbnail_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    checksum: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    metadata_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(64), default="imported", nullable=False)

    project: Mapped[Optional[Project]] = relationship(back_populates="media_assets")
    transcripts: Mapped[list[Transcript]] = relationship(back_populates="media_asset")
    highlights: Mapped[list[Highlight]] = relationship(back_populates="media_asset")
    clips: Mapped[list[Clip]] = relationship(back_populates="media_asset")


class SourceConnection(Base, TimestampMixin):
    __tablename__ = "source_connections"
    __table_args__ = (
        UniqueConstraint("platform", "external_account_id", name="uq_source_platform_account"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    platform: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    external_account_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    credential_ref: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    metadata_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    live_sessions: Mapped[list[LiveSession]] = relationship(back_populates="source_connection")


class LiveSession(Base, TimestampMixin):
    __tablename__ = "live_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source_connection_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("source_connections.id", ondelete="CASCADE"), nullable=False
    )
    stream_title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    stream_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(64), default="idle", nullable=False, index=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    recording_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    source_connection: Mapped[SourceConnection] = relationship(back_populates="live_sessions")


class ProcessingJob(Base, TimestampMixin):
    __tablename__ = "processing_jobs"
    __table_args__ = (
        Index("ix_processing_jobs_status_created", "status", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    job_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[ProcessingStatus] = mapped_column(
        Enum(ProcessingStatus),
        default=ProcessingStatus.PENDING,
        nullable=False,
        index=True,
    )
    progress: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    current_stage: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    source_ref: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    result_ref: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payload_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped[Optional[Project]] = relationship(back_populates="jobs")


class Transcript(Base, TimestampMixin):
    __tablename__ = "transcripts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    media_asset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("media_assets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    language: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    full_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    segments_json: Mapped[Optional[list[Any]]] = mapped_column(JSON, nullable=True)
    model_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(64), default="pending", nullable=False)

    media_asset: Mapped[MediaAsset] = relationship(back_populates="transcripts")


class Highlight(Base, TimestampMixin):
    __tablename__ = "highlights"
    __table_args__ = (
        Index("ix_highlights_media_score", "media_asset_id", "score"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    media_asset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("media_assets.id", ondelete="CASCADE"), nullable=False
    )
    start_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    end_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    transcript_excerpt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    detection_reasons_json: Mapped[Optional[list[Any]]] = mapped_column(JSON, nullable=True)
    source_ref: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(64), default="detected", nullable=False)

    media_asset: Mapped[MediaAsset] = relationship(back_populates="highlights")
    clips: Mapped[list[Clip]] = relationship(back_populates="highlight")


class Clip(Base, TimestampMixin):
    __tablename__ = "clips"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    media_asset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("media_assets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    highlight_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("highlights.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    start_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    end_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    aspect_ratio: Mapped[str] = mapped_column(String(16), default="9:16", nullable=False)
    file_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(64), default="draft", nullable=False)

    project: Mapped[Optional[Project]] = relationship(back_populates="clips")
    media_asset: Mapped[MediaAsset] = relationship(back_populates="clips")
    highlight: Mapped[Optional[Highlight]] = relationship(back_populates="clips")
    versions: Mapped[list[ClipVersion]] = relationship(back_populates="clip")
    subtitles: Mapped[list[Subtitle]] = relationship(back_populates="clip")
    exports: Mapped[list[Export]] = relationship(back_populates="clip")


class ClipVersion(Base, TimestampMixin):
    __tablename__ = "clip_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    clip_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("clips.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_label: Mapped[str] = mapped_column(String(128), nullable=False)
    file_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    settings_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    clip: Mapped[Clip] = relationship(back_populates="versions")


class Subtitle(Base, TimestampMixin):
    __tablename__ = "subtitles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    clip_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("clips.id", ondelete="CASCADE"), nullable=False, index=True
    )
    language: Mapped[str] = mapped_column(String(16), default="en", nullable=False)
    file_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    style_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    content_json: Mapped[Optional[list[Any]]] = mapped_column(JSON, nullable=True)

    clip: Mapped[Clip] = relationship(back_populates="subtitles")


class Export(Base, TimestampMixin):
    __tablename__ = "exports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    clip_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("clips.id", ondelete="CASCADE"), nullable=False, index=True
    )
    preset: Mapped[str] = mapped_column(String(64), nullable=False)
    aspect_ratio: Mapped[str] = mapped_column(String(16), nullable=False)
    resolution: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    file_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(64), default="pending", nullable=False)
    metadata_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    clip: Mapped[Clip] = relationship(back_populates="exports")


class AppSetting(Base, TimestampMixin):
    __tablename__ = "app_settings"
    __table_args__ = (UniqueConstraint("key", name="uq_app_settings_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    value_json: Mapped[Any] = mapped_column(JSON, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
