"""Live monitor orchestration: connections, sessions, rolling buffers."""

from __future__ import annotations

import secrets
import shutil
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.infrastructure.database.models import LiveSession, SourceConnection
from app.integrations.kick.adapter import KickAdapter
from app.integrations.twitch.adapter import TwitchAdapter
from app.integrations.youtube.adapter import YouTubeAdapter
from app.repositories.live_repository import LiveRepository
from app.workers.job_manager import job_manager

logger = get_logger(__name__)


class LiveService:
    def __init__(self, db: Session, settings: Settings | None = None) -> None:
        self._db = db
        self._settings = settings or get_settings()
        self._repo = LiveRepository(db)
        self._adapters = {
            "youtube": YouTubeAdapter(self._settings),
            "twitch": TwitchAdapter(self._settings),
            "kick": KickAdapter(self._settings),
        }
        self._buffers: dict[str, subprocess.Popen[Any]] = {}
        self._lock = threading.Lock()

    def platform_status(self) -> dict[str, Any]:
        status = {}
        for name, adapter in self._adapters.items():
            configured = getattr(adapter, "configured", lambda: False)()
            status[name] = {
                "configured": configured,
                "direct_av": adapter.supports_direct_av_ingest(),
                "capture": adapter.capture_guidance(),
            }
        return status

    def list_connections(self) -> list[dict[str, Any]]:
        return [LiveRepository.serialize_connection(c) for c in self._repo.list_connections()]

    def create_connection(
        self,
        *,
        platform: str,
        display_name: str,
        external_account_id: str | None = None,
        credential_ref: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if platform not in self._adapters:
            raise ValueError(f"Unsupported platform '{platform}'")
        row = self._repo.create_connection(
            platform=platform,
            display_name=display_name,
            external_account_id=external_account_id,
            credential_ref=credential_ref,
            metadata_json=metadata or {},
        )
        return LiveRepository.serialize_connection(row)

    def delete_connection(self, connection_id: str) -> None:
        row = self._repo.get_connection(connection_id)
        if row is None:
            raise LookupError("Source connection not found")
        self._repo.delete_connection(row)

    def oauth_start(self, platform: str, redirect_uri: str) -> dict[str, Any]:
        adapter = self._adapters.get(platform)
        if adapter is None:
            raise ValueError(f"Unsupported platform '{platform}'")
        if not getattr(adapter, "configured", lambda: False)():
            raise RuntimeError(
                f"{platform} OAuth is not configured. Set ACP_{platform.upper()}_CLIENT_ID/SECRET."
            )
        state = secrets.token_urlsafe(24)
        url = adapter.get_oauth_authorize_url(state, redirect_uri)
        return {"platform": platform, "authorize_url": url, "state": state}

    def oauth_callback(
        self,
        platform: str,
        *,
        code: str,
        redirect_uri: str,
        display_name: str | None = None,
    ) -> dict[str, Any]:
        adapter = self._adapters.get(platform)
        if adapter is None:
            raise ValueError(f"Unsupported platform '{platform}'")
        token_payload = adapter.exchange_code(code, redirect_uri)
        # Store token reference as opaque JSON in metadata; production should use
        # Windows Credential Manager (Phase later packaging). Local-first for now.
        connection = self._repo.create_connection(
            platform=platform,
            display_name=display_name or f"{platform} account",
            credential_ref=f"oauth:{platform}:{uuid4()}",
            metadata_json={
                "token": token_payload,
                "stored_at": datetime.now(timezone.utc).isoformat(),
                "storage": "database_dev_only",
            },
        )
        return LiveRepository.serialize_connection(connection)

    def refresh_status(self, connection_id: str) -> dict[str, Any]:
        connection = self._repo.get_connection(connection_id)
        if connection is None:
            raise LookupError("Source connection not found")
        adapter = self._adapters[connection.platform]
        token = ((connection.metadata_json or {}).get("token") or {}).get("access_token")
        if not token:
            raise RuntimeError("Connection has no access token. Complete OAuth first.")
        status = adapter.get_stream_status(token, connection.external_account_id)
        meta = dict(connection.metadata_json or {})
        meta["last_status"] = status
        connection.metadata_json = meta
        self._repo.save_connection(connection)
        return status

    def get_chat(self, connection_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        connection = self._repo.get_connection(connection_id)
        if connection is None:
            raise LookupError("Source connection not found")
        adapter = self._adapters[connection.platform]
        token = ((connection.metadata_json or {}).get("token") or {}).get("access_token")
        if not token:
            return []
        channel_id = connection.external_account_id or ""
        return adapter.get_chat_events(token, channel_id=channel_id, limit=limit)

    def start_local_capture_session(
        self,
        connection_id: str,
        *,
        input_url: str,
        title: str | None = None,
        rolling_seconds: int = 120,
    ) -> dict[str, Any]:
        """
        Start an authorized local capture into a rolling recording buffer.

        `input_url` may be an OBS virtual camera device path, a local media URL,
        or another user-authorized AV source. Platforms themselves are not scraped.
        """
        connection = self._repo.get_connection(connection_id)
        if connection is None:
            raise LookupError("Source connection not found")
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg is None:
            raise RuntimeError("ffmpeg required for local capture")

        session_id = str(uuid4())
        out_dir = self._settings.recordings_dir / session_id
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "rolling.mkv"

        # Segmented rolling buffer via ffmpeg segment muxer
        cmd = [
            ffmpeg,
            "-y",
            "-i",
            input_url,
            "-c",
            "copy",
            "-f",
            "segment",
            "-segment_time",
            str(max(10, rolling_seconds // 4)),
            "-reset_timestamps",
            "1",
            str(out_dir / "seg_%03d.mkv"),
        ]
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        with self._lock:
            self._buffers[session_id] = proc

        session = self._repo.create_session(
            id=session_id,
            source_connection_id=connection_id,
            stream_title=title or f"{connection.platform} capture",
            stream_url=input_url,
            status="recording",
            started_at=datetime.now(timezone.utc),
            recording_path=str(out_dir),
            metadata_json={
                "rolling_seconds": rolling_seconds,
                "mode": "authorized_local_capture",
                "pid": proc.pid,
            },
        )
        logger.info("live_capture_started", session_id=session_id, input=input_url)
        return LiveRepository.serialize_session(session)

    def stop_session(self, session_id: str) -> dict[str, Any]:
        session = self._repo.get_session(session_id)
        if session is None:
            raise LookupError("Live session not found")
        with self._lock:
            proc = self._buffers.pop(session_id, None)
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        session.status = "stopped"
        session.ended_at = datetime.now(timezone.utc)
        self._repo.save_session(session)
        return LiveRepository.serialize_session(session)

    def list_sessions(self) -> list[dict[str, Any]]:
        return [LiveRepository.serialize_session(s) for s in self._repo.list_sessions()]

    def enqueue_live_highlight_pass(self, session_id: str) -> dict[str, Any]:
        session = self._repo.get_session(session_id)
        if session is None:
            raise LookupError("Live session not found")
        # Concatenate recent segments into a temporary media asset-like path for analysis
        job = job_manager.enqueue(
            job_type="live_highlight_pass",
            source_ref=session_id,
            payload={"session_id": session_id},
        )
        from app.repositories.job_repository import JobRepository

        return JobRepository.serialize(job)

    def run_live_highlight_pass(
        self,
        session_id: str,
        progress=None,
    ) -> dict[str, Any]:
        from app.services.media_service import MediaService
        from app.services.transcription_service import TranscriptionService
        from app.services.semantic_analysis_service import SemanticAnalysisService
        from app.services.highlight_service import HighlightService
        from app.services.clip_service import ClipService

        session = self._repo.get_session(session_id)
        if session is None:
            raise LookupError("Live session not found")
        recording_dir = Path(session.recording_path or "")
        segments = sorted(recording_dir.glob("seg_*.mkv"))
        if not segments:
            raise FileNotFoundError("No rolling buffer segments available yet")

        def report(value: float, stage: str) -> None:
            if progress:
                progress(value, stage)

        report(5, "assembling_buffer")
        latest = segments[-1]
        # Import latest segment as media asset
        media = MediaService(self._db).import_local_file(
            latest,
            manage_original=True,
            display_name=f"live_{session_id}_{latest.name}",
        )
        media_id = media["id"]
        report(25, "transcribe")
        TranscriptionService(self._db).transcribe_asset(media_id, progress=lambda v, s: report(25 + v * 0.25, s))
        report(55, "semantic")
        try:
            SemanticAnalysisService(self._db).analyze_media(media_id, progress=lambda v, s: report(55 + v * 0.15, s))
        except Exception as exc:  # noqa: BLE001
            logger.warning("live_semantic_failed", error=str(exc))
        report(75, "highlights")
        highlights = HighlightService(self._db).detect_for_media(
            media_id, progress=lambda v, s: report(75 + v * 0.15, s)
        )
        report(90, "clips")
        clips = []
        if highlights:
            clips = ClipService(self._db).generate_from_highlights(
                media_id, max_duration=30, limit=3, progress=lambda v, s: report(90 + v * 0.1, s)
            )
        report(100, "completed")
        return {
            "session_id": session_id,
            "media_asset_id": media_id,
            "highlight_count": len(highlights),
            "clip_count": len(clips),
        }
