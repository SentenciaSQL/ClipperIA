"""Subtitle / caption generation and advanced editing."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

# deepcopy already imported for preset duplication

from sqlalchemy.orm import Session

from app.ai.transcription.whisper_provider import FasterWhisperProvider
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.media.audio import extract_wav_mono_16k
from app.repositories.audio_track_repository import AudioTrackRepository
from app.repositories.clip_repository import ClipRepository
from app.repositories.media_repository import MediaRepository
from app.repositories.transcript_repository import TranscriptRepository
from app.services.caption_presets import (
    CUSTOM_PRESETS_KEY,
    PLAY_RES_X,
    PLAY_RES_Y,
    apply_back_opacity,
    apply_text_opacity,
    hex_to_ass_bgr,
    list_presets,
    list_system_presets,
    new_custom_preset_id,
    normalize_style,
    resolve_preset,
)
from app.services.settings_service import SettingsService
from app.workers.job_manager import job_manager

logger = get_logger(__name__)

VOICE_CAPTION_KINDS = frozenset(
    {"original", "voiceover", "stem_vocals", "external", "narration"}
)


class SubtitleService:
    def __init__(self, db: Session, settings: Settings | None = None) -> None:
        self._db = db
        self._settings = settings or get_settings()
        self._clips = ClipRepository(db)
        self._transcripts = TranscriptRepository(db)
        self._tracks = AudioTrackRepository(db)
        self._media = MediaRepository(db)
        self._app_settings = SettingsService(db)

    def list_for_clip(self, clip_id: str) -> list[dict[str, Any]]:
        return [
            ClipRepository.serialize_subtitle(s)
            for s in self._clips.list_subtitles(clip_id)
        ]

    def _custom_presets_map(self) -> dict[str, Any]:
        raw = self._app_settings.get(CUSTOM_PRESETS_KEY)
        if isinstance(raw, dict):
            return dict(raw)
        return {}

    def presets(self) -> dict[str, Any]:
        custom = self._custom_presets_map()
        return {
            "system": list_system_presets(),
            "custom": {
                k: normalize_style({**v, "system": False, "id": k, "preset": k})
                for k, v in custom.items()
            },
            "all": list_presets(custom),
            "play_res": {"x": PLAY_RES_X, "y": PLAY_RES_Y},
        }

    def save_custom_preset(
        self,
        *,
        style: dict[str, Any],
        name: str | None = None,
        preset_id: str | None = None,
    ) -> dict[str, Any]:
        custom = self._custom_presets_map()
        label = (name or style.get("label") or "Custom").strip() or "Custom"
        if preset_id and preset_id in list_system_presets():
            # Saving edits of a system preset creates a new user preset
            preset_id = new_custom_preset_id(label)
        pid = preset_id or new_custom_preset_id(label)
        normalized = normalize_style(style)
        normalized["label"] = label
        normalized["preset"] = pid
        normalized["system"] = False
        normalized["id"] = pid
        # Never persist clip-specific source on reusable presets
        normalized.pop("source", None)
        custom[pid] = normalized
        self._app_settings.upsert(
            CUSTOM_PRESETS_KEY, custom, "User caption style presets"
        )
        return normalized

    def delete_custom_preset(self, preset_id: str) -> None:
        if preset_id in list_system_presets():
            raise ValueError("Cannot delete a system preset")
        custom = self._custom_presets_map()
        if preset_id not in custom:
            raise LookupError("Custom preset not found")
        custom.pop(preset_id)
        self._app_settings.upsert(
            CUSTOM_PRESETS_KEY, custom, "User caption style presets"
        )

    def duplicate_preset(self, preset_id: str, new_name: str | None = None) -> dict[str, Any]:
        all_presets = list_presets(self._custom_presets_map())
        if preset_id not in all_presets:
            raise LookupError("Preset not found")
        src = deepcopy(all_presets[preset_id])
        label = new_name or f"{src.get('label', preset_id)} (copy)"
        return self.save_custom_preset(style=src, name=label)

    def restore_system_preset(self, preset_id: str) -> dict[str, Any]:
        system = list_system_presets()
        if preset_id not in system:
            raise LookupError("Not a system preset")
        return system[preset_id]

    def apply_style_to_subtitle(
        self,
        subtitle_id: str,
        style: dict[str, Any],
        *,
        preset: str | None = None,
    ) -> dict[str, Any]:
        row = self._clips.get_subtitle(subtitle_id)
        if row is None:
            raise LookupError("Subtitle not found")
        cues = list(row.content_json or [])
        source = (row.style_json or {}).get("source")
        custom = self._custom_presets_map()
        style_final = resolve_preset(preset or style.get("preset"), style, custom=custom)
        if source:
            style_final["source"] = source
        return self.update_cues(subtitle_id, cues, style=style_final, preset=preset)

    def caption_sync_status(self, clip_id: str) -> dict[str, Any]:
        clip = self._clips.get(clip_id)
        if clip is None:
            raise LookupError("Clip not found")
        editor = dict(clip.editor_json or {})
        subs = self._clips.list_subtitles(clip_id)
        sub = subs[0] if subs else None
        style = dict((sub.style_json if sub else None) or {})
        source = dict(style.get("source") or editor.get("caption_source") or {})
        voice_id = editor.get("caption_voice_track_id") or source.get("track_id")
        tracks = self._tracks.list_for_clip(clip_id)
        voice_track = next((t for t in tracks if t.id == voice_id), None)
        if voice_track is None:
            voice_track = next(
                (t for t in tracks if t.kind in VOICE_CAPTION_KINDS and t.enabled and not t.muted),
                next((t for t in tracks if t.kind == "original"), None),
            )
        stale = bool(editor.get("captions_stale"))
        if sub and source:
            if voice_track is not None:
                if source.get("track_id") and source.get("track_id") != voice_track.id:
                    stale = True
                elif source.get("path") and voice_track.file_path and source.get("path") != voice_track.file_path:
                    stale = True
                elif source.get("kind") == "original" and voice_track.kind != "original":
                    stale = True
                elif source.get("kind") == "original" and voice_track.muted:
                    stale = True
        cues = list((sub.content_json if sub else None) or [])
        corrected = sum(1 for c in cues if c.get("manually_corrected"))
        return {
            "clip_id": clip_id,
            "has_captions": sub is not None,
            "subtitle_id": sub.id if sub else None,
            "captions_stale": stale,
            "caption_source": source or None,
            "caption_voice_track_id": voice_track.id if voice_track else None,
            "caption_voice_kind": voice_track.kind if voice_track else None,
            "manual_corrections": corrected,
            "cue_count": len(cues),
            "voice_tracks": [
                {
                    "id": t.id,
                    "name": t.name,
                    "kind": t.kind,
                    "enabled": t.enabled,
                    "muted": t.muted,
                    "file_path": t.file_path,
                }
                for t in tracks
                if t.kind in VOICE_CAPTION_KINDS
            ],
        }

    def mark_stale_if_voice_changed(
        self,
        clip_id: str,
        *,
        reason: str,
        track_id: str | None = None,
        track_kind: str | None = None,
    ) -> None:
        """Mark captions stale only when a voice-related source changes — not for music/sfx."""
        if track_kind and track_kind not in VOICE_CAPTION_KINDS:
            return
        clip = self._clips.get(clip_id)
        if clip is None:
            return
        subs = self._clips.list_subtitles(clip_id)
        if not subs:
            return
        editor = dict(clip.editor_json or {})
        source = dict(
            (subs[0].style_json or {}).get("source")
            or editor.get("caption_source")
            or {}
        )
        # Adding unrelated voice while captions still track original: mark stale
        if track_kind in {"voiceover", "stem_vocals", "narration", "external"}:
            if not source or source.get("kind") == "original" or (
                track_id and source.get("track_id") and source.get("track_id") != track_id
            ):
                editor["captions_stale"] = True
                editor["captions_stale_reason"] = reason
                clip.editor_json = editor
                self._clips.save(clip)
                return
        if track_id and source.get("track_id") and source.get("track_id") == track_id:
            editor["captions_stale"] = True
            editor["captions_stale_reason"] = reason
            clip.editor_json = editor
            self._clips.save(clip)

    def set_caption_voice_track(self, clip_id: str, track_id: str | None) -> dict[str, Any]:
        clip = self._clips.get(clip_id)
        if clip is None:
            raise LookupError("Clip not found")
        editor = dict(clip.editor_json or {})
        prev = editor.get("caption_voice_track_id")
        editor["caption_voice_track_id"] = track_id
        if track_id != prev and self._clips.list_subtitles(clip_id):
            editor["captions_stale"] = True
            editor["captions_stale_reason"] = "voice_track_selection_changed"
        clip.editor_json = editor
        self._clips.save(clip)
        return self.caption_sync_status(clip_id)

    def generate_from_transcript(
        self,
        clip_id: str,
        *,
        language: str = "en",
        style: dict[str, Any] | None = None,
        preset: str | None = None,
        replace_existing: bool = False,
        source_track_id: str | None = None,
    ) -> dict[str, Any]:
        clip = self._clips.get(clip_id)
        if clip is None:
            raise LookupError("Clip not found")

        existing = self._clips.list_subtitles(clip_id)
        if existing and not replace_existing:
            return ClipRepository.serialize_subtitle(existing[0])

        track = self._resolve_voice_track(clip_id, source_track_id)
        cues = self._cues_from_media_transcript(clip) if track is None or track.kind == "original" else None
        if cues is None:
            raise ValueError(
                "No transcript available for the original media. "
                "Use caption regenerate-preview with a voice track, or transcribe the media first."
            )

        preserved_style = None
        if existing:
            preserved_style = deepcopy(existing[0].style_json)
        custom = self._custom_presets_map()
        style_final = resolve_preset(
            preset or (preserved_style or {}).get("preset"),
            style
            or (
                {k: v for k, v in (preserved_style or {}).items() if k not in {"source", "preset"}}
                or None
            ),
            custom=custom,
        )
        if preset:
            style_final["preset"] = preset
        elif preserved_style and preserved_style.get("preset"):
            style_final["preset"] = preserved_style["preset"]
        style_final["source"] = self._source_meta(track, clip)

        return self._persist_cues(
            clip_id,
            cues,
            language=language,
            style_final=style_final,
            existing=existing[0] if existing and replace_existing else None,
            clear_stale=True,
        )

    def preview_regenerate(
        self,
        clip_id: str,
        *,
        source_track_id: str | None = None,
        language: str | None = None,
    ) -> dict[str, Any]:
        """Transcribe the selected voice track and return a draft for user review."""
        clip = self._clips.get(clip_id)
        if clip is None:
            raise LookupError("Clip not found")
        track = self._resolve_voice_track(clip_id, source_track_id)
        if track is None:
            raise ValueError("No voice track available for caption regeneration")

        existing = self._clips.list_subtitles(clip_id)
        current = list((existing[0].content_json if existing else None) or [])
        style = deepcopy((existing[0].style_json if existing else None) or resolve_preset("classic"))

        if track.kind == "original":
            proposed = self._cues_from_media_transcript(clip)
            if proposed is None:
                # Fall back to transcribing the media file for this clip window
                asset = self._media.get(clip.media_asset_id)
                if asset is None:
                    raise LookupError("Media asset not found")
                proposed = self._transcribe_file_to_cues(
                    Path(asset.file_path),
                    clip,
                    language=language,
                    cache_key=f"clip-{clip_id}-original",
                )
        else:
            if not track.file_path or not Path(track.file_path).is_file():
                raise FileNotFoundError("Voice track file missing")
            proposed = self._transcribe_file_to_cues(
                Path(track.file_path),
                clip,
                language=language,
                cache_key=f"track-{track.id}",
                timeline_offset=float(track.start_seconds or 0.0),
            )

        draft_id = uuid4().hex
        editor = dict(clip.editor_json or {})
        drafts = dict(editor.get("caption_drafts") or {})
        drafts[draft_id] = {
            "proposed_cues": proposed,
            "source_track_id": track.id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        # Keep only latest few drafts
        if len(drafts) > 5:
            for key in list(drafts.keys())[:-5]:
                drafts.pop(key, None)
        editor["caption_drafts"] = drafts
        editor["caption_voice_track_id"] = track.id
        clip.editor_json = editor
        self._clips.save(clip)

        return {
            "draft_id": draft_id,
            "source": self._source_meta(track, clip),
            "current_cues": current,
            "proposed_cues": proposed,
            "style": style,
            "manual_corrections_in_current": sum(
                1 for c in current if c.get("manually_corrected")
            ),
            "comparison": self._compare_cues(current, proposed),
        }

    def apply_regenerate(
        self,
        clip_id: str,
        *,
        draft_id: str | None = None,
        proposed_cues: list[dict[str, Any]] | None = None,
        source_track_id: str | None = None,
        keep_manual_corrections: bool = True,
        language: str = "en",
    ) -> dict[str, Any]:
        clip = self._clips.get(clip_id)
        if clip is None:
            raise LookupError("Clip not found")
        editor = dict(clip.editor_json or {})
        cues = proposed_cues
        track_id = source_track_id or editor.get("caption_voice_track_id")
        if draft_id:
            draft = (editor.get("caption_drafts") or {}).get(draft_id)
            if not draft:
                raise LookupError("Caption draft not found — preview again")
            cues = list(draft.get("proposed_cues") or [])
            track_id = draft.get("source_track_id") or track_id
        if cues is None:
            raise ValueError("No proposed cues to apply")

        existing = self._clips.list_subtitles(clip_id)
        current = list((existing[0].content_json if existing else None) or [])
        if keep_manual_corrections and current:
            cues = self._merge_manual_corrections(current, cues)

        track = self._resolve_voice_track(clip_id, track_id)
        preserved = deepcopy((existing[0].style_json if existing else None) or {})
        style_final = resolve_preset(
            preserved.get("preset"),
            {k: v for k, v in preserved.items() if k not in {"source", "preset"}} or None,
            custom=self._custom_presets_map(),
        )
        if preserved.get("preset"):
            style_final["preset"] = preserved["preset"]
        style_final["source"] = self._source_meta(track, clip)

        result = self._persist_cues(
            clip_id,
            cues,
            language=language,
            style_final=style_final,
            existing=existing[0] if existing else None,
            clear_stale=True,
        )
        # Drop applied draft
        if draft_id and editor.get("caption_drafts"):
            editor["caption_drafts"].pop(draft_id, None)
            clip.editor_json = editor
            self._clips.save(clip)
        return result

    def update_cues(
        self,
        subtitle_id: str,
        cues: list[dict[str, Any]],
        style: dict[str, Any] | None = None,
        preset: str | None = None,
    ) -> dict[str, Any]:
        row = self._clips.get_subtitle(subtitle_id)
        if row is None:
            raise LookupError("Subtitle not found")
        # Preserve correction metadata when clients send plain text edits
        previous = {i: c for i, c in enumerate(list(row.content_json or []))}
        normalized: list[dict[str, Any]] = []
        for i, cue in enumerate(cues):
            item = dict(cue)
            prev = previous.get(i)
            if prev is not None:
                old_text = str(prev.get("text") or "")
                new_text = str(item.get("text") or "")
                if new_text != old_text:
                    if not item.get("original_text"):
                        item["original_text"] = prev.get("original_text") or old_text
                    item["manually_corrected"] = True
                else:
                    if "original_text" not in item and prev.get("original_text"):
                        item["original_text"] = prev["original_text"]
                    if "manually_corrected" not in item and prev.get("manually_corrected"):
                        item["manually_corrected"] = prev["manually_corrected"]
            normalized.append(item)
        row.content_json = normalized
        if preset is not None or style is not None:
            base = dict(row.style_json or {})
            source = base.get("source")
            custom = self._custom_presets_map()
            row.style_json = resolve_preset(
                preset or base.get("preset"),
                style,
                custom=custom,
            )
            if preset:
                row.style_json["preset"] = preset
            if source:
                row.style_json["source"] = source
        style_final = normalize_style(row.style_json or resolve_preset("classic", custom=self._custom_presets_map()))
        if row.style_json and row.style_json.get("source"):
            style_final["source"] = row.style_json["source"]
        row.style_json = style_final
        self._write_sidecars(row.clip_id, normalized, style_final)
        row.file_path = str(self._settings.subtitles_dir / f"{row.clip_id}.ass")
        return ClipRepository.serialize_subtitle(self._clips.save_subtitle(row))

    def correct_cue_text(
        self,
        subtitle_id: str,
        cue_index: int,
        new_text: str,
        *,
        replace_phrase: str | None = None,
    ) -> dict[str, Any]:
        """Correct spelling/transcription without changing visual style."""
        row = self._clips.get_subtitle(subtitle_id)
        if row is None:
            raise LookupError("Subtitle not found")
        cues = list(row.content_json or [])
        if cue_index < 0 or cue_index >= len(cues):
            raise ValueError("Invalid cue index")
        cue = dict(cues[cue_index])
        current = str(cue.get("text") or "")
        if not cue.get("original_text"):
            cue["original_text"] = current
        if replace_phrase:
            if replace_phrase not in current:
                raise ValueError(f'Phrase "{replace_phrase}" not found in cue')
            cue["text"] = current.replace(replace_phrase, new_text, 1)
        else:
            cue["text"] = new_text
        cue["manually_corrected"] = True
        # Keep word timings but refresh word text if single-token replace
        if replace_phrase and cue.get("words"):
            words = []
            for w in cue["words"]:
                wt = dict(w)
                if str(wt.get("text") or "") == replace_phrase:
                    wt["text"] = new_text
                words.append(wt)
            cue["words"] = words
        cues[cue_index] = cue
        return self.update_cues(subtitle_id, cues)

    def restore_cue_text(self, subtitle_id: str, cue_index: int) -> dict[str, Any]:
        row = self._clips.get_subtitle(subtitle_id)
        if row is None:
            raise LookupError("Subtitle not found")
        cues = list(row.content_json or [])
        if cue_index < 0 or cue_index >= len(cues):
            raise ValueError("Invalid cue index")
        cue = dict(cues[cue_index])
        original = cue.get("original_text")
        if original is None:
            raise ValueError("Cue has no stored original text")
        cue["text"] = original
        cue["manually_corrected"] = False
        cues[cue_index] = cue
        return self.update_cues(subtitle_id, cues)

    def apply_word_override(
        self,
        subtitle_id: str,
        cue_index: int,
        override: dict[str, Any],
    ) -> dict[str, Any]:
        """Legacy visual override (style only). Prefer correct_cue_text for spelling fixes."""
        row = self._clips.get_subtitle(subtitle_id)
        if row is None:
            raise LookupError("Subtitle not found")
        cues = list(row.content_json or [])
        if cue_index < 0 or cue_index >= len(cues):
            raise ValueError("Invalid cue index")
        cue = dict(cues[cue_index])
        overrides = list(cue.get("overrides") or [])
        overrides.append(override)
        cue["overrides"] = overrides
        cues[cue_index] = cue
        return self.update_cues(subtitle_id, cues)

    def export_sidecar(self, clip_id: str, fmt: str = "srt") -> dict[str, Any]:
        subs = self._clips.list_subtitles(clip_id)
        if not subs:
            raise LookupError("No subtitles for clip")
        row = subs[0]
        cues = list(row.content_json or [])
        if fmt == "vtt":
            path = self._settings.subtitles_dir / f"{clip_id}.vtt"
            self._write_vtt(path, cues)
        else:
            path = self._settings.subtitles_dir / f"{clip_id}.srt"
            self._write_srt(path, cues)
        return {"format": fmt, "file_path": str(path)}

    def _persist_cues(
        self,
        clip_id: str,
        cues: list[dict[str, Any]],
        *,
        language: str,
        style_final: dict[str, Any],
        existing: Any | None,
        clear_stale: bool,
    ) -> dict[str, Any]:
        self._write_sidecars(clip_id, cues, style_final)
        ass_path = self._settings.subtitles_dir / f"{clip_id}.ass"
        if existing is not None:
            existing.language = language
            existing.file_path = str(ass_path)
            existing.style_json = style_final
            existing.content_json = cues
            row = self._clips.save_subtitle(existing)
        else:
            row = self._clips.add_subtitle(
                clip_id=clip_id,
                language=language,
                file_path=str(ass_path),
                style_json=style_final,
                content_json=cues,
            )
        if clear_stale:
            clip = self._clips.get(clip_id)
            if clip is not None:
                editor = dict(clip.editor_json or {})
                editor["captions_stale"] = False
                editor.pop("captions_stale_reason", None)
                editor["caption_source"] = style_final.get("source")
                editor["caption_voice_track_id"] = (style_final.get("source") or {}).get(
                    "track_id"
                )
                editor["active_subtitle_id"] = row.id
                clip.editor_json = editor
                self._clips.save(clip)
        payload = ClipRepository.serialize_subtitle(row)
        payload["srt_path"] = str(self._settings.subtitles_dir / f"{clip_id}.srt")
        payload["vtt_path"] = str(self._settings.subtitles_dir / f"{clip_id}.vtt")
        return payload

    def _write_sidecars(
        self, clip_id: str, cues: list[dict[str, Any]], style: dict[str, Any]
    ) -> None:
        srt_path = self._settings.subtitles_dir / f"{clip_id}.srt"
        ass_path = self._settings.subtitles_dir / f"{clip_id}.ass"
        vtt_path = self._settings.subtitles_dir / f"{clip_id}.vtt"
        self._write_srt(srt_path, cues)
        self._write_vtt(vtt_path, cues)
        self._write_ass(ass_path, cues, style)

    def _resolve_voice_track(self, clip_id: str, track_id: str | None) -> Any | None:
        tracks = self._tracks.list_for_clip(clip_id)
        if track_id:
            match = next((t for t in tracks if t.id == track_id), None)
            if match is None:
                raise LookupError("Audio track not found")
            return match
        clip = self._clips.get(clip_id)
        editor = dict((clip.editor_json if clip else None) or {})
        preferred = editor.get("caption_voice_track_id")
        if preferred:
            match = next((t for t in tracks if t.id == preferred), None)
            if match is not None:
                return match
        for kind in ("voiceover", "stem_vocals", "narration", "original"):
            match = next(
                (t for t in tracks if t.kind == kind and t.enabled and not t.muted),
                None,
            )
            if match is not None:
                return match
        return next((t for t in tracks if t.kind == "original"), None)

    def _source_meta(self, track: Any | None, clip: Any) -> dict[str, Any]:
        if track is None:
            return {
                "track_id": None,
                "kind": "original",
                "path": None,
                "clip_id": clip.id,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
        return {
            "track_id": track.id,
            "kind": track.kind,
            "path": track.file_path,
            "name": track.name,
            "clip_id": clip.id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _cues_from_media_transcript(self, clip: Any) -> list[dict[str, Any]] | None:
        transcript = self._transcripts.latest_for_media(clip.media_asset_id)
        if transcript is None:
            return None
        segments = (transcript.segments_json or {}).get("segments") or []
        return self._segments_to_cues(segments, clip, timeline_offset=0.0)

    def _transcribe_file_to_cues(
        self,
        source: Path,
        clip: Any,
        *,
        language: str | None,
        cache_key: str,
        timeline_offset: float = 0.0,
    ) -> list[dict[str, Any]]:
        wav = self._settings.cache_dir / "caption_audio" / f"{cache_key}.wav"
        extract_wav_mono_16k(source, wav)
        job_manager.acquire_gpu()
        try:
            result = FasterWhisperProvider(self._settings).transcribe(
                str(wav),
                model_size=self._settings.whisper_model_size,
                language=language,
                vad_filter=True,
            )
        finally:
            job_manager.release_gpu()
        segments = result.get("segments") or []
        # External voice files are usually already clip-local; still clamp to clip duration
        duration = max(0.1, float(clip.end_seconds) - float(clip.start_seconds))
        cues: list[dict[str, Any]] = []
        for seg in segments:
            start = float(seg.get("start") or 0) + timeline_offset
            end = float(seg.get("end") or start) + timeline_offset
            if end < 0 or start > duration:
                continue
            text = str(seg.get("text") or "").strip()
            if not text:
                continue
            words = []
            for w in seg.get("words") or []:
                wt = str(w.get("word") or w.get("text") or "").strip()
                if not wt:
                    continue
                words.append(
                    {
                        "text": wt,
                        "start": max(0.0, float(w.get("start") or start) + timeline_offset),
                        "end": max(0.0, float(w.get("end") or end) + timeline_offset),
                    }
                )
            cues.append(
                {
                    "start": max(0.0, start),
                    "end": min(duration, max(0.0, end)),
                    "text": text,
                    "words": words,
                    "overrides": [],
                    "manually_corrected": False,
                }
            )
        return cues

    def _segments_to_cues(
        self,
        segments: list[dict[str, Any]],
        clip: Any,
        *,
        timeline_offset: float,
    ) -> list[dict[str, Any]]:
        cues: list[dict[str, Any]] = []
        for seg in segments:
            start = float(seg.get("start") or 0)
            end = float(seg.get("end") or start)
            if end < clip.start_seconds or start > clip.end_seconds:
                continue
            text = str(seg.get("text") or "").strip()
            if not text:
                continue
            words = []
            for w in seg.get("words") or []:
                ws = float(w.get("start") or start)
                we = float(w.get("end") or end)
                wt = str(w.get("word") or w.get("text") or "").strip()
                if not wt:
                    continue
                words.append(
                    {
                        "text": wt,
                        "start": max(0.0, ws - clip.start_seconds) + timeline_offset,
                        "end": max(0.0, we - clip.start_seconds) + timeline_offset,
                    }
                )
            cues.append(
                {
                    "start": max(0.0, start - clip.start_seconds) + timeline_offset,
                    "end": max(0.0, end - clip.start_seconds) + timeline_offset,
                    "text": text,
                    "words": words,
                    "overrides": [],
                    "manually_corrected": False,
                }
            )
        return cues

    @staticmethod
    def _compare_cues(
        current: list[dict[str, Any]], proposed: list[dict[str, Any]]
    ) -> dict[str, Any]:
        return {
            "current_count": len(current),
            "proposed_count": len(proposed),
            "current_sample": [c.get("text") for c in current[:5]],
            "proposed_sample": [c.get("text") for c in proposed[:5]],
        }

    @staticmethod
    def _merge_manual_corrections(
        current: list[dict[str, Any]], proposed: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Re-apply manual text corrections onto new cues by original_text / time overlap."""
        corrections = [
            c
            for c in current
            if c.get("manually_corrected") and c.get("original_text")
        ]
        if not corrections:
            return proposed
        merged: list[dict[str, Any]] = []
        for cue in proposed:
            item = dict(cue)
            text = str(item.get("text") or "")
            for corr in corrections:
                original = str(corr.get("original_text") or "")
                corrected = str(corr.get("text") or "")
                if original and original in text:
                    item["text"] = text.replace(original, corrected)
                    item["original_text"] = original
                    item["manually_corrected"] = True
                    break
                # time-overlap fallback for whole-cue edits
                cs, ce = float(corr.get("start") or 0), float(corr.get("end") or 0)
                ps, pe = float(item.get("start") or 0), float(item.get("end") or 0)
                if ce > ps and pe > cs and abs((ce - cs) - (pe - ps)) < 1.5:
                    if original and text.strip() == original.strip():
                        item["text"] = corrected
                        item["original_text"] = original
                        item["manually_corrected"] = True
                        break
            merged.append(item)
        return merged

    @staticmethod
    def _format_srt_ts(seconds: float) -> str:
        ms = int(round(seconds * 1000))
        h, rem = divmod(ms, 3_600_000)
        m, rem = divmod(rem, 60_000)
        s, milli = divmod(rem, 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{milli:03d}"

    @staticmethod
    def _format_vtt_ts(seconds: float) -> str:
        ms = int(round(seconds * 1000))
        h, rem = divmod(ms, 3_600_000)
        m, rem = divmod(rem, 60_000)
        s, milli = divmod(rem, 1000)
        return f"{h:02d}:{m:02d}:{s:02d}.{milli:03d}"

    @staticmethod
    def _format_ass_ts(seconds: float) -> str:
        cs = int(round(seconds * 100))
        h, rem = divmod(cs, 360_000)
        m, rem = divmod(rem, 6_000)
        s, centi = divmod(rem, 100)
        return f"{h:d}:{m:02d}:{s:02d}.{centi:02d}"

    def _write_srt(self, path: Path, cues: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        lines: list[str] = []
        for idx, cue in enumerate(cues, start=1):
            lines.append(str(idx))
            lines.append(
                f"{self._format_srt_ts(float(cue['start']))} --> {self._format_srt_ts(float(cue['end']))}"
            )
            lines.append(str(cue["text"]))
            lines.append("")
        path.write_text("\n".join(lines), encoding="utf-8")

    def _write_vtt(self, path: Path, cues: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = ["WEBVTT", ""]
        for cue in cues:
            lines.append(
                f"{self._format_vtt_ts(float(cue['start']))} --> {self._format_vtt_ts(float(cue['end']))}"
            )
            lines.append(str(cue["text"]))
            lines.append("")
        path.write_text("\n".join(lines), encoding="utf-8")

    def _write_ass(self, path: Path, cues: list[dict[str, Any]], style: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        style = normalize_style(style)
        bold = 1 if style.get("bold") or int(style.get("font_weight") or 400) >= 600 else 0
        italic = 1 if style.get("italic") else 0
        outline = int(style.get("outline", 3))
        shadow = int(style.get("shadow", 0))
        border_style = int(style.get("border_style", 1))
        if float(style.get("background_opacity") or 0) > 0.05 and border_style == 1:
            # Prefer opaque box when background opacity is set
            border_style = 3
        primary = apply_text_opacity(
            str(style.get("primary_colour") or "&H00FFFFFF"),
            float(style.get("text_opacity", 1.0)),
        )
        back = apply_back_opacity(
            str(style.get("back_colour") or "&H64000000"),
            float(style.get("background_opacity", 0.0)),
        )
        spacing = float(style.get("letter_spacing") or 0.0)
        margin_l = int(style.get("margin_l", 40))
        margin_r = int(style.get("margin_r", 40))
        margin_v = int(style.get("margin_v", 80))
        max_width = int(style.get("max_width") or PLAY_RES_X)
        # Derive side margins from max_width when centered-ish
        if max_width < PLAY_RES_X:
            side = max(0, (PLAY_RES_X - max_width) // 2)
            margin_l = max(margin_l, side)
            margin_r = max(margin_r, side)
        pad = int(style.get("padding") or 0)
        if pad:
            margin_l = max(0, margin_l - pad)
            margin_r = max(0, margin_r - pad)

        header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {PLAY_RES_X}
PlayResY: {PLAY_RES_Y}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{style.get('font_name','Arial')},{int(style.get('font_size',48))},{primary},&H000000FF,{style.get('outline_colour','&H00000000')},{back},{bold},{italic},0,0,100,100,{spacing:.2f},0,{border_style},{outline},{shadow},{int(style.get('alignment',2))},{margin_l},{margin_r},{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        pos_x = style.get("pos_x")
        pos_y = style.get("pos_y")
        anim_in = str(style.get("animation_in") or "none")
        anim_out = str(style.get("animation_out") or "none")
        anim_dur = float(style.get("animation_duration") or 0.25)
        events = []
        for cue in cues:
            text = self._render_ass_text(
                str(cue.get("text") or ""), cue.get("overrides") or [], style
            )
            tags: list[str] = []
            if pos_x is not None and pos_y is not None:
                tags.append(f"\\pos({float(pos_x):.1f},{float(pos_y):.1f})")
            # Simple fade in/out mapped from animation settings
            cue_dur = max(0.05, float(cue.get("end") or 0) - float(cue.get("start") or 0))
            fade_in_ms = int(anim_dur * 1000) if anim_in in {"fade", "pop"} else 0
            fade_out_ms = int(anim_dur * 1000) if anim_out in {"fade", "pop"} else 0
            if fade_in_ms or fade_out_ms:
                fade_in_ms = min(fade_in_ms, int(cue_dur * 400))
                fade_out_ms = min(fade_out_ms, int(cue_dur * 400))
                tags.append(f"\\fad({fade_in_ms},{fade_out_ms})")
            if anim_in == "pop":
                tags.append(r"\t(0,180,\fscx110\fscy110)\t(180,280,\fscx100\fscy100)")
            prefix = f"{{{''.join(tags)}}}" if tags else ""
            events.append(
                "Dialogue: 0,"
                f"{self._format_ass_ts(float(cue['start']))},"
                f"{self._format_ass_ts(float(cue['end']))},"
                f"Default,,0,0,0,,{prefix}{text}"
            )
        path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")

    def _render_ass_text(
        self,
        text: str,
        overrides: list[dict[str, Any]],
        base_style: dict[str, Any],
    ) -> str:
        """Apply optional visual ASS tags; content corrections live in cue.text itself."""
        if not overrides:
            return text.replace("\n", r"\N")

        spans: list[tuple[int, int, dict[str, Any]]] = []
        for ov in overrides:
            start = int(ov.get("start_char", 0))
            end = int(ov.get("end_char", start))
            if end <= start or start < 0:
                phrase = str(ov.get("text") or "")
                if phrase and phrase in text:
                    start = text.index(phrase)
                    end = start + len(phrase)
                else:
                    continue
            spans.append((start, min(end, len(text)), ov.get("style") or ov))
        if not spans:
            return text.replace("\n", r"\N")
        spans.sort(key=lambda s: s[0])

        parts: list[str] = []
        cursor = 0
        for start, end, style in spans:
            if start > cursor:
                parts.append(self._escape_ass(text[cursor:start]))
            tag = self._ass_override_tags(style, base_style)
            parts.append(f"{{{tag}}}{self._escape_ass(text[start:end])}{{\\r}}")
            cursor = end
        if cursor < len(text):
            parts.append(self._escape_ass(text[cursor:]))
        return "".join(parts).replace("\n", r"\N")

    @staticmethod
    def _escape_ass(value: str) -> str:
        return value.replace("{", "(").replace("}", ")")

    @staticmethod
    def _ass_override_tags(style: dict[str, Any], base: dict[str, Any]) -> str:
        tags: list[str] = []
        if "color" in style or "primary_colour" in style:
            color = style.get("primary_colour") or hex_to_ass_bgr(str(style.get("color")))
            tags.append(f"\\c{color}")
        if "font_size" in style or "size" in style:
            tags.append(
                f"\\fs{int(style.get('font_size') or style.get('size') or base.get('font_size', 48))}"
            )
        if "font_name" in style or "font" in style:
            tags.append(f"\\fn{style.get('font_name') or style.get('font')}")
        if "bold" in style:
            tags.append(f"\\b{1 if style.get('bold') else 0}")
        if "outline" in style:
            tags.append(f"\\bord{style.get('outline')}")
        if "shadow" in style:
            tags.append(f"\\shad{style.get('shadow')}")
        return "".join(tags)
