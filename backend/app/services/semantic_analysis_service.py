"""Semantic analysis of transcript candidate windows via Ollama/Qwen3."""

from __future__ import annotations

import json
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.ai.providers.ollama_provider import OllamaProvider
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.repositories.media_repository import MediaRepository
from app.repositories.transcript_repository import TranscriptRepository
from app.workers.job_manager import job_manager

logger = get_logger(__name__)


class SemanticAnalysisService:
    def __init__(self, db: Session, settings: Settings | None = None) -> None:
        self._db = db
        self._settings = settings or get_settings()
        self._media = MediaRepository(db)
        self._transcripts = TranscriptRepository(db)
        self._ollama = OllamaProvider(self._settings)

    def provider_status(self) -> dict[str, Any]:
        return {
            "provider": "ollama",
            "base_url": self._settings.ollama_base_url,
            "configured_model": self._settings.ollama_model,
            "available": self._ollama.available(),
            "models": self._ollama.list_models(),
        }

    def enqueue(self, media_asset_id: str) -> dict[str, Any]:
        asset = self._media.get(media_asset_id)
        if asset is None:
            raise LookupError("Media asset not found")
        if self._transcripts.latest_for_media(media_asset_id) is None:
            raise ValueError("Transcript required before semantic analysis")
        job = job_manager.enqueue(
            job_type="semantic_analysis",
            project_id=asset.project_id,
            source_ref=asset.id,
            payload={"media_asset_id": media_asset_id},
        )
        from app.repositories.job_repository import JobRepository

        return JobRepository.serialize(job)

    def analyze_media(
        self,
        media_asset_id: str,
        *,
        progress: Callable[[float, str], None] | None = None,
    ) -> dict[str, Any]:
        asset = self._media.get(media_asset_id)
        if asset is None:
            raise LookupError("Media asset not found")
        transcript = self._transcripts.latest_for_media(media_asset_id)
        if transcript is None:
            raise ValueError("Transcript required before semantic analysis")

        def report(value: float, stage: str) -> None:
            if progress:
                progress(value, stage)

        report(10, "building_candidates")
        segments = (transcript.segments_json or {}).get("segments") or []
        windows = self._build_candidate_windows(segments)
        report(30, "semantic_analysis")

        if self._ollama.available():
            analysis = self._analyze_with_ollama(windows, transcript.full_text or "")
            provider = "ollama"
        else:
            analysis = self._analyze_with_local_heuristic(windows)
            provider = "local_heuristic"
            logger.warning(
                "ollama_unavailable_using_local_heuristic",
                media_asset_id=media_asset_id,
            )

        report(90, "persisting_analysis")
        meta = dict(transcript.segments_json or {})
        meta["semantic_analysis"] = {
            "provider": provider,
            "model": self._settings.ollama_model if provider == "ollama" else "keyword-heuristic",
            "windows": windows,
            "result": analysis,
        }
        transcript.segments_json = meta
        self._transcripts.save(transcript)
        report(100, "completed")
        return meta["semantic_analysis"]

    def _build_candidate_windows(
        self,
        segments: list[dict[str, Any]],
        *,
        window_seconds: float = 20.0,
    ) -> list[dict[str, Any]]:
        if not segments:
            return []
        windows: list[dict[str, Any]] = []
        current: list[dict[str, Any]] = []
        window_start = float(segments[0].get("start") or 0.0)

        for seg in segments:
            start = float(seg.get("start") or 0.0)
            end = float(seg.get("end") or start)
            if current and end - window_start >= window_seconds:
                windows.append(self._window_payload(current, window_start))
                current = []
                window_start = start
            current.append(seg)
        if current:
            windows.append(self._window_payload(current, window_start))
        return windows

    @staticmethod
    def _window_payload(segments: list[dict[str, Any]], start: float) -> dict[str, Any]:
        end = float(segments[-1].get("end") or start)
        text = " ".join(str(s.get("text") or "").strip() for s in segments).strip()
        return {
            "start": start,
            "end": end,
            "text": text,
            "segment_count": len(segments),
        }

    def _analyze_with_ollama(
        self,
        windows: list[dict[str, Any]],
        full_text: str,
    ) -> dict[str, Any]:
        prompt = (
            "You are a video clipping assistant. Analyze candidate transcript windows "
            "and return JSON with key 'moments', an array of objects with fields: "
            "start, end, score (0-1), reason, tags (array), humor (0-1), emotion (0-1), "
            "surprise (0-1), narrative_quality (0-1). "
            "Only use provided window timestamps. Focus on interesting conversational "
            "moments, reactions, humor, and story continuity.\n\n"
            f"FULL_TEXT:\n{full_text[:4000]}\n\n"
            f"WINDOWS_JSON:\n{json.dumps(windows[:40])}\n"
        )
        return self._ollama.analyze_segments(prompt)

    def _analyze_with_local_heuristic(self, windows: list[dict[str, Any]]) -> dict[str, Any]:
        keywords = {
            "wow",
            "amazing",
            "insane",
            "laugh",
            "funny",
            "wait",
            "what",
            "omg",
            "crazy",
            "clip",
            "highlight",
            "goal",
            "win",
            "lose",
            "joke",
        }
        moments = []
        for window in windows:
            text = (window.get("text") or "").lower()
            tokens = set(text.replace(",", " ").replace(".", " ").split())
            hits = sorted(tokens & keywords)
            density = len(text.split())
            score = min(1.0, 0.15 * len(hits) + min(density, 40) / 80.0)
            if score < 0.2 and density < 8:
                continue
            moments.append(
                {
                    "start": window["start"],
                    "end": window["end"],
                    "score": round(score, 3),
                    "reason": (
                        f"Keyword/density heuristic hits={hits}" if hits else "Speech density"
                    ),
                    "tags": hits,
                    "humor": 0.6 if hits else 0.2,
                    "emotion": 0.5 if hits else 0.25,
                    "surprise": 0.55 if "wow" in hits or "what" in hits else 0.2,
                    "narrative_quality": min(1.0, density / 30.0),
                }
            )
        moments.sort(key=lambda m: m["score"], reverse=True)
        return {"moments": moments, "note": "Ollama unavailable; local heuristic used"}
