"""Subtitle / caption generation and advanced editing."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.repositories.clip_repository import ClipRepository
from app.repositories.transcript_repository import TranscriptRepository
from app.services.caption_presets import hex_to_ass_bgr, list_presets, resolve_preset


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

    def presets(self) -> dict[str, Any]:
        return list_presets()

    def generate_from_transcript(
        self,
        clip_id: str,
        *,
        language: str = "en",
        style: dict[str, Any] | None = None,
        preset: str | None = None,
        replace_existing: bool = False,
    ) -> dict[str, Any]:
        clip = self._clips.get(clip_id)
        if clip is None:
            raise LookupError("Clip not found")
        transcript = self._transcripts.latest_for_media(clip.media_asset_id)
        if transcript is None:
            raise ValueError("Transcript required to generate captions")

        existing = self._clips.list_subtitles(clip_id)
        if existing and not replace_existing:
            # Preserve manual edits; return latest unless user opts to replace
            return ClipRepository.serialize_subtitle(existing[0])

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
                        "start": max(0.0, ws - clip.start_seconds),
                        "end": max(0.0, we - clip.start_seconds),
                    }
                )
            cues.append(
                {
                    "start": max(0.0, start - clip.start_seconds),
                    "end": max(0.0, end - clip.start_seconds),
                    "text": text,
                    "words": words,
                    "overrides": [],
                }
            )

        style_final = resolve_preset(preset, style)
        srt_path = self._settings.subtitles_dir / f"{clip_id}.srt"
        ass_path = self._settings.subtitles_dir / f"{clip_id}.ass"
        vtt_path = self._settings.subtitles_dir / f"{clip_id}.vtt"
        self._write_srt(srt_path, cues)
        self._write_vtt(vtt_path, cues)
        self._write_ass(ass_path, cues, style_final)

        row = self._clips.add_subtitle(
            clip_id=clip_id,
            language=language,
            file_path=str(ass_path),
            style_json=style_final,
            content_json=cues,
        )
        payload = ClipRepository.serialize_subtitle(row)
        payload["srt_path"] = str(srt_path)
        payload["vtt_path"] = str(vtt_path)
        return payload

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
        row.content_json = cues
        if preset is not None or style is not None:
            row.style_json = resolve_preset(preset or (row.style_json or {}).get("preset"), style)
            if preset:
                row.style_json["preset"] = preset
        style_final = row.style_json or resolve_preset("classic")
        srt_path = self._settings.subtitles_dir / f"{row.clip_id}.srt"
        ass_path = self._settings.subtitles_dir / f"{row.clip_id}.ass"
        vtt_path = self._settings.subtitles_dir / f"{row.clip_id}.vtt"
        self._write_srt(srt_path, cues)
        self._write_vtt(vtt_path, cues)
        self._write_ass(ass_path, cues, style_final)
        row.file_path = str(ass_path)
        return ClipRepository.serialize_subtitle(self._clips.save_subtitle(row))

    def apply_word_override(
        self,
        subtitle_id: str,
        cue_index: int,
        override: dict[str, Any],
    ) -> dict[str, Any]:
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
        bold = 1 if style.get("bold") else 0
        outline = int(style.get("outline", 3))
        shadow = int(style.get("shadow", 0))
        border_style = int(style.get("border_style", 1))
        header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{style.get('font_name','Arial')},{style.get('font_size',48)},{style.get('primary_colour','&H00FFFFFF')},&H000000FF,{style.get('outline_colour','&H00000000')},{style.get('back_colour','&H64000000')},{bold},0,0,0,100,100,0,0,{border_style},{outline},{shadow},{style.get('alignment',2)},40,40,{style.get('margin_v',80)},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        events = []
        for cue in cues:
            text = self._render_ass_text(str(cue.get("text") or ""), cue.get("overrides") or [], style)
            events.append(
                "Dialogue: 0,"
                f"{self._format_ass_ts(float(cue['start']))},"
                f"{self._format_ass_ts(float(cue['end']))},"
                f"Default,,0,0,0,,{text}"
            )
        path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")

    def _render_ass_text(
        self,
        text: str,
        overrides: list[dict[str, Any]],
        base_style: dict[str, Any],
    ) -> str:
        """Apply word/phrase overrides via inline ASS tags; inherit unset props."""
        if not overrides:
            return text.replace("\n", r"\N")

        # Build spans by character range
        spans: list[tuple[int, int, dict[str, Any]]] = []
        for ov in overrides:
            start = int(ov.get("start_char", 0))
            end = int(ov.get("end_char", start))
            if end <= start or start < 0:
                # Also allow match by exact word/phrase
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
            tags.append(f"\\fs{int(style.get('font_size') or style.get('size') or base.get('font_size', 48))}")
        if "font_name" in style or "font" in style:
            tags.append(f"\\fn{style.get('font_name') or style.get('font')}")
        if "bold" in style:
            tags.append(f"\\b{1 if style.get('bold') else 0}")
        if "outline" in style:
            tags.append(f"\\bord{style.get('outline')}")
        if "shadow" in style:
            tags.append(f"\\shad{style.get('shadow')}")
        return "".join(tags)
