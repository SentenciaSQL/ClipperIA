"""Subtitle / caption generation and editing."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.repositories.clip_repository import ClipRepository
from app.repositories.transcript_repository import TranscriptRepository


class SubtitleService:
    def __init__(self, db: Session, settings: Settings | None = None) -> None:
        self._db = db
        self._settings = settings or get_settings()
        self._clips = ClipRepository(db)
        self._transcripts = TranscriptRepository(db)

    def list_for_clip(self, clip_id: str) -> list[dict[str, Any]]:
        return [
            ClipRepository.serialize_subtitle(s)
            for s in self._clips.list_subtitles(clip_id)
        ]

    def generate_from_transcript(
        self,
        clip_id: str,
        *,
        language: str = "en",
        style: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        clip = self._clips.get(clip_id)
        if clip is None:
            raise LookupError("Clip not found")
        transcript = self._transcripts.latest_for_media(clip.media_asset_id)
        if transcript is None:
            raise ValueError("Transcript required to generate captions")

        segments = (transcript.segments_json or {}).get("segments") or []
        cues = []
        for seg in segments:
            start = float(seg.get("start") or 0)
            end = float(seg.get("end") or start)
            if end < clip.start_seconds or start > clip.end_seconds:
                continue
            text = str(seg.get("text") or "").strip()
            if not text:
                continue
            cues.append(
                {
                    "start": max(0.0, start - clip.start_seconds),
                    "end": max(0.0, end - clip.start_seconds),
                    "text": text,
                }
            )

        style = style or {
            "font_name": "Arial",
            "font_size": 48,
            "primary_colour": "&H00FFFFFF",
            "outline_colour": "&H00000000",
            "alignment": 2,
            "margin_v": 80,
        }
        srt_path = self._settings.subtitles_dir / f"{clip_id}.srt"
        ass_path = self._settings.subtitles_dir / f"{clip_id}.ass"
        self._write_srt(srt_path, cues)
        self._write_ass(ass_path, cues, style)

        row = self._clips.add_subtitle(
            clip_id=clip_id,
            language=language,
            file_path=str(ass_path),
            style_json=style,
            content_json=cues,
        )
        payload = ClipRepository.serialize_subtitle(row)
        payload["srt_path"] = str(srt_path)
        return payload

    def update_cues(
        self,
        subtitle_id: str,
        cues: list[dict[str, Any]],
        style: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        row = self._clips.get_subtitle(subtitle_id)
        if row is None:
            raise LookupError("Subtitle not found")
        row.content_json = cues
        if style is not None:
            row.style_json = style
        style_final = row.style_json or {}
        srt_path = self._settings.subtitles_dir / f"{row.clip_id}.srt"
        ass_path = self._settings.subtitles_dir / f"{row.clip_id}.ass"
        self._write_srt(srt_path, cues)
        self._write_ass(ass_path, cues, style_final)
        row.file_path = str(ass_path)
        return ClipRepository.serialize_subtitle(self._clips.save_subtitle(row))

    @staticmethod
    def _format_srt_ts(seconds: float) -> str:
        ms = int(round(seconds * 1000))
        h, rem = divmod(ms, 3_600_000)
        m, rem = divmod(rem, 60_000)
        s, milli = divmod(rem, 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{milli:03d}"

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

    def _write_ass(self, path: Path, cues: list[dict[str, Any]], style: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{style.get('font_name','Arial')},{style.get('font_size',48)},{style.get('primary_colour','&H00FFFFFF')},&H000000FF,{style.get('outline_colour','&H00000000')},&H64000000,0,0,0,0,100,100,0,0,1,3,0,{style.get('alignment',2)},40,40,{style.get('margin_v',80)},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        events = []
        for cue in cues:
            text = str(cue["text"]).replace("\n", r"\N")
            events.append(
                "Dialogue: 0,"
                f"{self._format_ass_ts(float(cue['start']))},"
                f"{self._format_ass_ts(float(cue['end']))},"
                f"Default,,0,0,0,,{text}"
            )
        path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")
