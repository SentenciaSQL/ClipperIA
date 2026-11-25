"""Highlight detection and ranking service."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.ai.detection.audio_intensity import analyze_audio_intensity
from app.ai.detection.visual_events import detect_visual_changes
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.media.audio import extract_wav_mono_16k
from app.repositories.highlight_repository import HighlightRepository
from app.repositories.media_repository import MediaRepository
from app.repositories.transcript_repository import TranscriptRepository
from app.workers.job_manager import job_manager

logger = get_logger(__name__)


class HighlightService:
    def __init__(self, db: Session, settings: Settings | None = None) -> None:
        self._db = db
        self._settings = settings or get_settings()
        self._media = MediaRepository(db)
        self._transcripts = TranscriptRepository(db)
        self._highlights = HighlightRepository(db)

    def list_highlights(
        self,
        *,
        media_asset_id: str | None = None,
    ) -> list[dict[str, Any]]:
        if media_asset_id:
            rows = self._highlights.list_for_media(media_asset_id)
        else:
            rows = self._highlights.list_all()
        return [HighlightRepository.serialize(r) for r in rows]

    def update_status(self, highlight_id: str, status: str) -> dict[str, Any]:
        row = self._highlights.get(highlight_id)
        if row is None:
            raise LookupError("Highlight not found")
        row.status = status
        return HighlightRepository.serialize(self._highlights.save(row))

    def enqueue(self, media_asset_id: str) -> dict[str, Any]:
        asset = self._media.get(media_asset_id)
        if asset is None:
            raise LookupError("Media asset not found")
        job = job_manager.enqueue(
            job_type="detect_highlights",
            project_id=asset.project_id,
            source_ref=asset.id,
            payload={"media_asset_id": media_asset_id},
        )
        from app.repositories.job_repository import JobRepository

        return JobRepository.serialize(job)

    def detect_for_media(
        self,
        media_asset_id: str,
        *,
        progress: Callable[[float, str], None] | None = None,
        replace_existing: bool = True,
    ) -> list[dict[str, Any]]:
        asset = self._media.get(media_asset_id)
        if asset is None:
            raise LookupError("Media asset not found")
        source = Path(asset.file_path)
        if not source.is_file():
            raise FileNotFoundError("Media file missing on disk")

        def report(value: float, stage: str) -> None:
            if progress:
                progress(value, stage)

        report(5, "preparing_audio")
        audio_path = self._settings.cache_dir / "audio" / f"{asset.id}.wav"
        if not audio_path.is_file():
            extract_wav_mono_16k(source, audio_path)

        report(20, "audio_intensity")
        intensity = analyze_audio_intensity(audio_path)

        report(35, "visual_events")
        visual = detect_visual_changes(source)

        transcript = self._transcripts.latest_for_media(media_asset_id)
        segments = ((transcript.segments_json or {}).get("segments") if transcript else None) or []
        vad = ((transcript.segments_json or {}).get("vad_segments") if transcript else None) or []
        semantic = (
            ((transcript.segments_json or {}).get("semantic_analysis") if transcript else None)
            or {}
        )
        moments = semantic.get("result", {}).get("moments") or []

        report(55, "scoring_candidates")
        candidates = self._build_candidates(
            duration=float(asset.duration_seconds or 0),
            intensity=intensity,
            visual=visual,
            segments=segments,
            vad=vad,
            moments=moments,
            transcript_text=transcript.full_text if transcript else None,
        )
        candidates = self._deduplicate(candidates)

        report(80, "persisting_highlights")
        if replace_existing:
            self._highlights.delete_for_media(media_asset_id)

        saved: list[dict[str, Any]] = []
        for cand in candidates:
            row = self._highlights.create(
                media_asset_id=media_asset_id,
                start_seconds=cand["start"],
                end_seconds=cand["end"],
                score=cand["score"],
                transcript_excerpt=cand.get("transcript"),
                detection_reasons_json=cand.get("reasons"),
                source_ref=media_asset_id,
                status="detected",
            )
            saved.append(HighlightRepository.serialize(row))

        asset.status = "highlights_ready"
        self._media.save(asset)
        report(100, "completed")
        return saved

    def _build_candidates(
        self,
        *,
        duration: float,
        intensity: list[dict[str, Any]],
        visual: list[dict[str, Any]],
        segments: list[dict[str, Any]],
        vad: list[dict[str, Any]],
        moments: list[dict[str, Any]],
        transcript_text: str | None,
    ) -> list[dict[str, Any]]:
        settings = self._settings
        window = 12.0
        if duration <= 0:
            duration = max(
                [float(i.get("end") or 0) for i in intensity]
                + [float(v.get("end") or 0) for v in visual]
                + [float(s.get("end") or 0) for s in segments]
                + [window],
            )

        # Seed candidate centers from peaks + semantic moments + visual events
        centers: list[float] = []
        if intensity:
            ranked = sorted(intensity, key=lambda x: x.get("intensity", 0), reverse=True)
            centers.extend(float(x["start"]) for x in ranked[:8])
        centers.extend(float(m.get("start") or 0) for m in moments[:8])
        centers.extend(float(v.get("start") or 0) for v in visual[:8])
        if not centers and duration > 0:
            centers = [0.0, max(0.0, duration / 2 - window / 2)]

        candidates: list[dict[str, Any]] = []
        for center in centers:
            start = max(0.0, center)
            end = min(duration if duration > 0 else start + window, start + window)
            if end - start < 3:
                continue

            audio_score = self._window_metric(intensity, start, end, key="intensity")
            voice_score = self._overlap_ratio(vad, start, end)
            visual_score = self._window_metric(visual, start, end, key="score")
            semantic_hit = self._semantic_for_window(moments, start, end)
            semantic_score = float(semantic_hit.get("score") or 0.0)
            narrative_score = float(semantic_hit.get("narrative_quality") or semantic_score)
            chat_score = 0.0  # chat arrives in Phase 7

            # Voice/emotion blends VAD presence with semantic emotion cues
            emotion = float(semantic_hit.get("emotion") or 0.0)
            voice_emotion = min(1.0, 0.6 * voice_score + 0.4 * emotion)

            score = (
                settings.score_audio_intensity * audio_score
                + settings.score_voice_emotion * voice_emotion
                + settings.score_semantic * semantic_score
                + settings.score_chat_activity * chat_score
                + settings.score_visual_changes * visual_score
                + settings.score_narrative_quality * narrative_score
            )

            excerpt = self._transcript_excerpt(segments, start, end) or (
                semantic_hit.get("reason") if semantic_hit else None
            )
            reasons = [
                {"signal": "audio_intensity", "value": round(audio_score, 3)},
                {"signal": "voice_emotion", "value": round(voice_emotion, 3)},
                {"signal": "semantic", "value": round(semantic_score, 3)},
                {"signal": "visual_changes", "value": round(visual_score, 3)},
                {"signal": "narrative_quality", "value": round(narrative_score, 3)},
                {"signal": "chat_activity", "value": round(chat_score, 3)},
            ]
            if semantic_hit.get("reason"):
                reasons.append({"signal": "semantic_reason", "value": semantic_hit["reason"]})

            candidates.append(
                {
                    "start": round(start, 3),
                    "end": round(end, 3),
                    "score": round(float(score), 4),
                    "transcript": excerpt,
                    "reasons": reasons,
                }
            )

        candidates.sort(key=lambda c: c["score"], reverse=True)
        return candidates[:20]

    def _deduplicate(
        self,
        candidates: list[dict[str, Any]],
        *,
        iou_threshold: float = 0.45,
    ) -> list[dict[str, Any]]:
        kept: list[dict[str, Any]] = []
        for cand in candidates:
            overlap = False
            for existing in kept:
                if self._iou(cand, existing) >= iou_threshold:
                    overlap = True
                    break
            if not overlap:
                kept.append(cand)
        return kept

    @staticmethod
    def _iou(a: dict[str, Any], b: dict[str, Any]) -> float:
        start = max(float(a["start"]), float(b["start"]))
        end = min(float(a["end"]), float(b["end"]))
        inter = max(0.0, end - start)
        if inter <= 0:
            return 0.0
        union = (float(a["end"]) - float(a["start"])) + (float(b["end"]) - float(b["start"])) - inter
        return inter / union if union > 0 else 0.0

    @staticmethod
    def _window_metric(
        rows: list[dict[str, Any]],
        start: float,
        end: float,
        *,
        key: str,
    ) -> float:
        values = [
            float(r.get(key) or 0.0)
            for r in rows
            if float(r.get("end") or 0) >= start and float(r.get("start") or 0) <= end
        ]
        if not values:
            return 0.0
        return max(values)

    @staticmethod
    def _overlap_ratio(rows: list[dict[str, Any]], start: float, end: float) -> float:
        if end <= start:
            return 0.0
        covered = 0.0
        for row in rows:
            s = max(start, float(row.get("start") or 0))
            e = min(end, float(row.get("end") or 0))
            if e > s:
                covered += e - s
        return min(1.0, covered / (end - start))

    @staticmethod
    def _semantic_for_window(
        moments: list[dict[str, Any]],
        start: float,
        end: float,
    ) -> dict[str, Any]:
        best: dict[str, Any] = {}
        best_score = -1.0
        for moment in moments:
            ms = float(moment.get("start") or 0)
            me = float(moment.get("end") or ms)
            if me < start or ms > end:
                continue
            score = float(moment.get("score") or 0)
            if score > best_score:
                best_score = score
                best = moment
        return best

    @staticmethod
    def _transcript_excerpt(
        segments: list[dict[str, Any]],
        start: float,
        end: float,
    ) -> str | None:
        texts = [
            str(s.get("text") or "").strip()
            for s in segments
            if float(s.get("end") or 0) >= start and float(s.get("start") or 0) <= end
        ]
        text = " ".join(t for t in texts if t).strip()
        return text or None
