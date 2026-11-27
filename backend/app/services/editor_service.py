"""Clip editor state: opacity, keyframes, mixer, composition helpers."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.media.encoding import EncodeRequest
from app.repositories.clip_repository import ClipRepository
from app.repositories.media_repository import MediaRepository
from app.services.audio_track_service import AudioTrackService
from app.services.subtitle_service import SubtitleService

DEFAULT_EDITOR: dict[str, Any] = {
    "opacity": 1.0,
    "opacity_keyframes": [],
    "zoom": 1.0,
    "crop_box": None,
    "master_volume": 1.0,
    "normalize_audio": False,
    "ducking": False,
    "burn_captions": True,
    "export_captions_sidecar": False,
    "caption_preset": "classic",
    "active_subtitle_id": None,
    "caption_voice_track_id": None,
    "captions_stale": False,
    "caption_source": None,
}


class EditorService:
    def __init__(self, db: Session, settings: Settings | None = None) -> None:
        self._db = db
        self._settings = settings or get_settings()
        self._clips = ClipRepository(db)
        self._media = MediaRepository(db)
        self._audio = AudioTrackService(db, settings)
        self._subs = SubtitleService(db, settings)

    def get_editor(self, clip_id: str) -> dict[str, Any]:
        clip = self._clips.get(clip_id)
        if clip is None:
            raise LookupError("Clip not found")
        state = deepcopy(DEFAULT_EDITOR)
        if clip.editor_json:
            state.update(clip.editor_json)
        self._audio.ensure_original_track(clip_id)
        sync = self._subs.caption_sync_status(clip_id)
        # Reflect live stale detection into editor payload
        state["captions_stale"] = bool(sync.get("captions_stale"))
        if sync.get("caption_source"):
            state["caption_source"] = sync["caption_source"]
        if sync.get("caption_voice_track_id"):
            state["caption_voice_track_id"] = sync["caption_voice_track_id"]
        return {
            "clip_id": clip_id,
            "editor": state,
            "audio_tracks": self._audio.list_tracks(clip_id),
            "subtitles": self._subs.list_for_clip(clip_id),
            "caption_presets": self._subs.presets(),
            "caption_sync": sync,
        }

    def update_editor(self, clip_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        clip = self._clips.get(clip_id)
        if clip is None:
            raise LookupError("Clip not found")
        state = deepcopy(DEFAULT_EDITOR)
        if clip.editor_json:
            state.update(clip.editor_json)
        for key in DEFAULT_EDITOR:
            if key in patch:
                state[key] = patch[key]
        if "opacity" in state:
            state["opacity"] = max(0.0, min(1.0, float(state["opacity"])))
        if "master_volume" in state:
            state["master_volume"] = max(0.0, min(2.0, float(state["master_volume"])))
        # validate keyframes
        kfs = []
        for item in state.get("opacity_keyframes") or []:
            kfs.append(
                {
                    "t": float(item.get("t", 0.0)),
                    "opacity": max(0.0, min(1.0, float(item.get("opacity", 1.0)))),
                }
            )
        state["opacity_keyframes"] = sorted(kfs, key=lambda x: x["t"])
        clip.editor_json = state
        self._clips.save(clip)
        return self.get_editor(clip_id)

    def build_encode_request(
        self,
        clip_id: str,
        *,
        destination: Path,
        settings: dict[str, Any] | None = None,
        preset_size: tuple[int, int] | None = None,
        fps: int = 30,
        video_bitrate: str = "8M",
        audio_bitrate: str = "192k",
        aspect_ratio: str | None = None,
    ) -> EncodeRequest:
        clip = self._clips.get(clip_id)
        if clip is None:
            raise LookupError("Clip not found")
        asset = self._media.get(clip.media_asset_id)
        if asset is None:
            raise LookupError("Media asset not found")
        settings = settings or {}
        editor = deepcopy(DEFAULT_EDITOR)
        if clip.editor_json:
            editor.update(clip.editor_json)

        start = float(settings.get("start_seconds", clip.start_seconds))
        end = float(settings.get("end_seconds", clip.end_seconds))
        duration = max(0.1, end - start)

        burn = None
        if bool(settings.get("burn_captions", editor.get("burn_captions", True))):
            if settings.get("subtitle_path"):
                burn = Path(settings["subtitle_path"])
            else:
                subs = self._clips.list_subtitles(clip_id)
                if editor.get("active_subtitle_id"):
                    match = next((s for s in subs if s.id == editor["active_subtitle_id"]), None)
                    if match and match.file_path:
                        burn = Path(match.file_path)
                elif subs and subs[0].file_path:
                    burn = Path(subs[0].file_path)

        include_source, source_vol, source_delay_ms, mix = self._audio.build_mix_inputs(
            clip_id, for_export=True, clip_duration=duration
        )
        # Optional ducking: reduce non-voice tracks when vocals/voiceover present
        if editor.get("ducking"):
            has_voice = any(
                t.get("kind") in {"stem_vocals", "voiceover"} and t.get("enabled") and not t.get("muted")
                for t in self._audio.list_tracks(clip_id)
            )
            if has_voice:
                for item in mix:
                    # heuristic: lower music/sfx
                    if item.volume > 0:
                        item.volume = min(item.volume, 0.35)

        width = height = None
        if preset_size:
            width, height = preset_size

        return EncodeRequest(
            source=Path(asset.file_path),
            destination=destination,
            start_seconds=start,
            end_seconds=end,
            aspect_ratio=str(aspect_ratio or settings.get("aspect_ratio") or clip.aspect_ratio),
            width=width,
            height=height,
            fps=fps,
            video_bitrate=video_bitrate,
            audio_bitrate=audio_bitrate,
            burn_subtitles=burn if burn and burn.is_file() else None,
            crop_box=settings.get("crop_box", editor.get("crop_box")),
            zoom=float(settings.get("zoom", editor.get("zoom", 1.0))),
            opacity=float(settings.get("opacity", editor.get("opacity", 1.0))),
            opacity_keyframes=list(
                settings.get("opacity_keyframes", editor.get("opacity_keyframes") or [])
            ),
            master_volume=float(settings.get("master_volume", editor.get("master_volume", 1.0))),
            normalize_audio=bool(
                settings.get("normalize_audio", editor.get("normalize_audio", False))
            ),
            include_source_audio=include_source,
            source_audio_volume=source_vol,
            source_audio_delay_ms=source_delay_ms,
            audio_mix=mix,
            audio_source=Path(settings["audio_path"])
            if settings.get("audio_path") and not mix
            else None,
        )
