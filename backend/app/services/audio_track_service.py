"""Audio track CRUD, import, Demucs stems, and mix planning."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.media.demucs_separator import DemucsSeparator
from app.media.encoding import AudioMixInput
from app.repositories.audio_track_repository import AudioTrackRepository
from app.repositories.clip_repository import ClipRepository
from app.repositories.media_repository import MediaRepository
from app.workers.job_manager import job_manager

logger = get_logger(__name__)

ALLOWED_AUDIO_EXT = {".mp3", ".wav", ".aac", ".m4a", ".flac", ".ogg"}


class AudioTrackService:
    def __init__(self, db: Session, settings: Settings | None = None) -> None:
        self._db = db
        self._settings = settings or get_settings()
        self._tracks = AudioTrackRepository(db)
        self._clips = ClipRepository(db)
        self._media = MediaRepository(db)

    def list_tracks(self, clip_id: str) -> list[dict[str, Any]]:
        if self._clips.get(clip_id) is None:
            raise LookupError("Clip not found")
        return [AudioTrackRepository.serialize(t) for t in self._tracks.list_for_clip(clip_id)]

    def ensure_original_track(self, clip_id: str) -> dict[str, Any]:
        clip = self._clips.get(clip_id)
        if clip is None:
            raise LookupError("Clip not found")
        existing = [t for t in self._tracks.list_for_clip(clip_id) if t.kind == "original"]
        if existing:
            return AudioTrackRepository.serialize(existing[0])
        asset = self._media.get(clip.media_asset_id)
        row = self._tracks.create(
            clip_id=clip_id,
            name="Original audio",
            kind="original",
            file_path=asset.file_path if asset else None,
            enabled=True,
            muted=False,
            exclude_from_export=False,
            volume=1.0,
            sort_order=0,
        )
        return AudioTrackRepository.serialize(row)

    def create_track(
        self,
        clip_id: str,
        *,
        name: str,
        kind: str = "music",
        file_path: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        if self._clips.get(clip_id) is None:
            raise LookupError("Clip not found")
        tracks = self._tracks.list_for_clip(clip_id)
        row = self._tracks.create(
            clip_id=clip_id,
            name=name,
            kind=kind,
            file_path=file_path,
            enabled=bool(kwargs.get("enabled", True)),
            muted=bool(kwargs.get("muted", False)),
            exclude_from_export=bool(kwargs.get("exclude_from_export", False)),
            volume=float(kwargs.get("volume", 1.0)),
            fade_in_seconds=float(kwargs.get("fade_in_seconds", 0.0)),
            fade_out_seconds=float(kwargs.get("fade_out_seconds", 0.0)),
            start_seconds=float(kwargs.get("start_seconds", 0.0)),
            trim_start_seconds=float(kwargs.get("trim_start_seconds", 0.0)),
            trim_end_seconds=kwargs.get("trim_end_seconds"),
            sync_offset_seconds=float(kwargs.get("sync_offset_seconds", 0.0)),
            locked=bool(kwargs.get("locked", False)),
            sort_order=int(kwargs.get("sort_order", len(tracks))),
            meta_json=kwargs.get("meta"),
        )
        return AudioTrackRepository.serialize(row)

    def update_track(self, track_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        row = self._tracks.get(track_id)
        if row is None:
            raise LookupError("Audio track not found")
        # offset_seconds is the user-facing alias for timeline start_seconds
        if "offset_seconds" in patch and "start_seconds" not in patch:
            patch = {**patch, "start_seconds": float(patch["offset_seconds"])}
        if row.locked and patch.get("locked") is not False:
            # Allow unlock; block destructive edits while locked
            allowed = {"locked", "enabled", "muted", "volume"}
            if any(k not in allowed for k in patch if k != "offset_seconds"):
                raise ValueError("Track is locked")
        prev_muted = row.muted
        prev_path = row.file_path
        for key in (
            "name",
            "kind",
            "file_path",
            "enabled",
            "muted",
            "exclude_from_export",
            "volume",
            "fade_in_seconds",
            "fade_out_seconds",
            "start_seconds",
            "trim_start_seconds",
            "trim_end_seconds",
            "sync_offset_seconds",
            "locked",
            "sort_order",
        ):
            if key in patch:
                setattr(row, key, patch[key])
        if "meta" in patch:
            row.meta_json = patch["meta"]
        if row.volume is not None:
            row.volume = max(0.0, min(2.0, float(row.volume)))
        if row.start_seconds is not None:
            row.start_seconds = max(0.0, float(row.start_seconds))
        saved = self._tracks.save(row)
        # Voice-source changes can desync captions; music/sfx do not
        from app.services.subtitle_service import VOICE_CAPTION_KINDS, SubtitleService

        if saved.kind in VOICE_CAPTION_KINDS:
            reason = None
            if prev_path != saved.file_path:
                reason = "voice_track_file_changed"
            elif (not prev_muted) and saved.muted:
                reason = "voice_track_muted"
            if reason:
                SubtitleService(self._db, self._settings).mark_stale_if_voice_changed(
                    saved.clip_id,
                    reason=reason,
                    track_id=saved.id,
                    track_kind=saved.kind,
                )
        return AudioTrackRepository.serialize(saved)

    def duplicate_track(self, track_id: str) -> dict[str, Any]:
        row = self._tracks.get(track_id)
        if row is None:
            raise LookupError("Audio track not found")
        return self.create_track(
            row.clip_id,
            name=f"{row.name} (copy)",
            kind=row.kind,
            file_path=row.file_path,
            enabled=row.enabled,
            muted=row.muted,
            exclude_from_export=row.exclude_from_export,
            volume=row.volume,
            fade_in_seconds=row.fade_in_seconds,
            fade_out_seconds=row.fade_out_seconds,
            start_seconds=row.start_seconds,
            trim_start_seconds=row.trim_start_seconds,
            trim_end_seconds=row.trim_end_seconds,
            sync_offset_seconds=row.sync_offset_seconds,
            sort_order=row.sort_order + 1,
            meta=row.meta_json,
        )

    def delete_track(self, track_id: str) -> None:
        row = self._tracks.get(track_id)
        if row is None:
            raise LookupError("Audio track not found")
        if row.kind == "original":
            raise ValueError("Cannot delete the original audio track; mute or exclude it instead")
        if row.locked:
            raise ValueError("Track is locked")
        self._tracks.delete(row)

    def import_audio_file(self, clip_id: str, source_path: str, *, name: str | None = None, kind: str = "music") -> dict[str, Any]:
        clip = self._clips.get(clip_id)
        if clip is None:
            raise LookupError("Clip not found")
        src = Path(source_path)
        if not src.is_file():
            raise FileNotFoundError(f"Audio file missing: {source_path}")
        if src.suffix.lower() not in ALLOWED_AUDIO_EXT:
            raise ValueError(f"Unsupported audio type '{src.suffix}'")
        dest_dir = self._settings.cache_dir / "audio_imports" / clip_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"{uuid4().hex}{src.suffix.lower()}"
        shutil.copy2(src, dest)
        created = self.create_track(
            clip_id,
            name=name or src.stem,
            kind=kind,
            file_path=str(dest),
        )
        from app.services.subtitle_service import VOICE_CAPTION_KINDS, SubtitleService

        if kind in VOICE_CAPTION_KINDS:
            SubtitleService(self._db, self._settings).mark_stale_if_voice_changed(
                clip_id,
                reason="voice_track_imported",
                track_id=created.get("id"),
                track_kind=kind,
            )
        return created

    def enqueue_demucs(self, clip_id: str) -> dict[str, Any]:
        clip = self._clips.get(clip_id)
        if clip is None:
            raise LookupError("Clip not found")
        if not DemucsSeparator().available():
            raise RuntimeError(
                "Demucs is not installed. In the backend venv run: pip install demucs"
            )
        job = job_manager.enqueue(
            job_type="separate_audio",
            project_id=clip.project_id,
            source_ref=clip_id,
            payload={"clip_id": clip_id},
        )
        from app.repositories.job_repository import JobRepository

        return JobRepository.serialize(job)

    def run_demucs(
        self,
        clip_id: str,
        *,
        progress: Callable[[float, str], None] | None = None,
    ) -> dict[str, Any]:
        clip = self._clips.get(clip_id)
        if clip is None:
            raise LookupError("Clip not found")
        asset = self._media.get(clip.media_asset_id)
        if asset is None:
            raise LookupError("Media asset not found")

        def report(v: float, s: str) -> None:
            if progress:
                progress(v, s)

        report(5, "starting_demucs")
        separator = DemucsSeparator()
        result = separator.separate(
            Path(asset.file_path),
            self._settings.cache_dir / "demucs" / clip_id,
        )
        report(80, "persisting_stems")
        created = []
        stem_kind_map = {
            "vocals": "stem_vocals",
            "drums": "stem_drums",
            "bass": "stem_bass",
            "other": "stem_other",
            "no_vocals": "stem_other",
        }
        for stem_name, path in (result.get("stems") or {}).items():
            kind = stem_kind_map.get(stem_name, "external")
            created.append(
                self.create_track(
                    clip_id,
                    name=f"Stem: {stem_name}",
                    kind=kind,
                    file_path=path,
                    meta={"demucs": True, "stem": stem_name, "model": result.get("model")},
                )
            )
        # Mute original by default after separation so user can keep vocals + new music
        original = next(
            (t for t in self._tracks.list_for_clip(clip_id) if t.kind == "original"),
            None,
        )
        if original is None:
            self.ensure_original_track(clip_id)
            original = next(
                (t for t in self._tracks.list_for_clip(clip_id) if t.kind == "original"),
                None,
            )
        if original is not None:
            original.muted = True
            self._tracks.save(original)
        report(100, "completed")
        return {"stems": result, "tracks": created}

    def build_mix_inputs(
        self,
        clip_id: str,
        *,
        for_export: bool = True,
        clip_duration: float | None = None,
    ) -> tuple[bool, float, int, list[AudioMixInput]]:
        """
        Returns (include_source_audio, source_volume, source_delay_ms, extra_mix_inputs).

        Original track uses source audio from the video input (index 0).
        Offset (`start_seconds`) delays when that track begins on the clip timeline.
        Other tracks become extra ffmpeg inputs.
        """
        tracks = self._tracks.list_for_clip(clip_id)
        if not tracks:
            return True, 1.0, 0, []

        include_source = False
        source_volume = 0.0
        source_delay_ms = 0
        extras: list[AudioMixInput] = []
        for track in tracks:
            if not track.enabled or track.muted:
                continue
            if for_export and track.exclude_from_export:
                continue
            if track.kind == "original":
                include_source = True
                source_volume = float(track.volume)
                source_delay_ms = int(
                    max(0.0, (track.start_seconds + track.sync_offset_seconds) * 1000)
                )
                continue
            if not track.file_path or not Path(track.file_path).is_file():
                continue
            # Offset = when the track starts on the clip timeline (independent of trim)
            delay_ms = int(max(0.0, (track.start_seconds + track.sync_offset_seconds) * 1000))
            trim_dur = None
            if track.trim_end_seconds is not None:
                trim_dur = max(0.0, float(track.trim_end_seconds) - float(track.trim_start_seconds))
            elif clip_duration is not None:
                trim_dur = max(0.0, clip_duration - float(track.start_seconds))
            extras.append(
                AudioMixInput(
                    path=Path(track.file_path),
                    volume=float(track.volume),
                    fade_in_seconds=float(track.fade_in_seconds),
                    fade_out_seconds=float(track.fade_out_seconds),
                    delay_ms=delay_ms,
                    trim_start_seconds=float(track.trim_start_seconds),
                    trim_duration_seconds=trim_dur,
                )
            )
        return include_source, source_volume, source_delay_ms, extras
