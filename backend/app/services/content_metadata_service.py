"""AI-generated clip descriptions and hashtag suggestions."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.ai.providers.registry import ProviderRegistry
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.repositories.clip_repository import ClipRepository
from app.repositories.highlight_repository import HighlightRepository
from app.repositories.media_repository import MediaRepository
from app.repositories.transcript_repository import TranscriptRepository

logger = get_logger(__name__)


class ContentMetadataService:
    def __init__(self, db: Session, settings: Settings | None = None) -> None:
        self._db = db
        self._settings = settings or get_settings()
        self._clips = ClipRepository(db)
        self._media = MediaRepository(db)
        self._transcripts = TranscriptRepository(db)
        self._highlights = HighlightRepository(db)
        self._providers = ProviderRegistry(self._settings)

    def generate_for_clip(
        self,
        clip_id: str,
        *,
        provider: str | None = None,
        platform: str = "tiktok",
    ) -> dict[str, Any]:
        clip = self._clips.get(clip_id)
        if clip is None:
            raise LookupError("Clip not found")
        asset = self._media.get(clip.media_asset_id)
        transcript = self._transcripts.latest_for_media(clip.media_asset_id)
        excerpt = ""
        if transcript and transcript.segments_json:
            segments = transcript.segments_json.get("segments") or []
            parts = []
            for seg in segments:
                start = float(seg.get("start") or 0)
                end = float(seg.get("end") or start)
                if end < clip.start_seconds or start > clip.end_seconds:
                    continue
                text = str(seg.get("text") or "").strip()
                if text:
                    parts.append(text)
            excerpt = " ".join(parts).strip()
        if not excerpt and transcript:
            excerpt = (transcript.full_text or "")[:800]

        highlight_reason = None
        if clip.highlight_id:
            hl = self._highlights.get(clip.highlight_id)
            if hl:
                highlight_reason = hl.detection_reasons_json

        prompt = (
            "Create social posting metadata for a short video clip. "
            "Return JSON with keys: title, description, hashtags (array of strings without #), "
            "hooks (array of short opening lines), cta (string). "
            f"Target platform: {platform}. Keep description under 300 characters.\n\n"
            f"Clip title: {clip.title}\n"
            f"Duration: {clip.end_seconds - clip.start_seconds:.1f}s\n"
            f"Source file: {(asset.original_filename if asset else 'unknown')}\n"
            f"Transcript excerpt: {excerpt or 'n/a'}\n"
            f"Detection context: {highlight_reason or 'n/a'}\n"
        )

        try:
            provider_name, llm = self._providers.get_llm(provider)
            result = llm.analyze_segments(prompt)
            source = provider_name
        except Exception as exc:  # noqa: BLE001
            logger.warning("metadata_llm_unavailable", error=str(exc))
            result = self._heuristic(excerpt or clip.title, platform)
            source = "local_heuristic"

        payload = {
            "clip_id": clip_id,
            "platform": platform,
            "provider": source,
            "title": result.get("title") or clip.title,
            "description": result.get("description")
            or f"Watch this moment from {clip.title}",
            "hashtags": result.get("hashtags")
            or ["shorts", "clip", "viral", platform.replace("_", "")],
            "hooks": result.get("hooks") or ["Wait for it…", "You won't believe this"],
            "cta": result.get("cta") or "Follow for more clips",
            "raw": result,
        }
        # Persist on a clip version settings blob for later export packaging
        self._clips.add_version(
            clip_id=clip_id,
            version_label=f"metadata-{platform}",
            file_path=clip.file_path,
            settings_json={"content_metadata": payload},
            is_primary=False,
        )
        return payload

    @staticmethod
    def _heuristic(text: str, platform: str) -> dict[str, Any]:
        words = [w.strip(".,!?").lower() for w in text.split() if len(w) > 3]
        uniq = []
        for w in words:
            if w not in uniq:
                uniq.append(w)
            if len(uniq) >= 6:
                break
        tags = uniq + ["shorts", "highlight", platform]
        return {
            "title": (text[:60] + "…") if len(text) > 60 else (text or "New clip"),
            "description": text[:280] or "AI-selected highlight clip",
            "hashtags": tags[:12],
            "hooks": ["This moment though", "Clip of the day"],
            "cta": "Save and share",
        }
