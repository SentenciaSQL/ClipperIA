"""Reusable caption style presets."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

# ASS colours are &HAABBGGRR
CAPTION_PRESETS: dict[str, dict[str, Any]] = {
    "classic": {
        "label": "Classic",
        "font_name": "Arial",
        "font_size": 48,
        "bold": 0,
        "primary_colour": "&H00FFFFFF",
        "outline_colour": "&H00000000",
        "back_colour": "&H64000000",
        "outline": 3,
        "shadow": 0,
        "alignment": 2,
        "margin_v": 80,
        "background_opacity": 0.4,
    },
    "modern": {
        "label": "Modern",
        "font_name": "Montserrat",
        "font_size": 52,
        "bold": 1,
        "primary_colour": "&H00FFFFFF",
        "outline_colour": "&H00222222",
        "back_colour": "&H00000000",
        "outline": 0,
        "shadow": 2,
        "alignment": 2,
        "margin_v": 100,
        "background_opacity": 0.0,
    },
    "tiktok": {
        "label": "TikTok",
        "font_name": "Arial Black",
        "font_size": 56,
        "bold": 1,
        "primary_colour": "&H00FFFFFF",
        "outline_colour": "&H00000000",
        "back_colour": "&H00000000",
        "outline": 4,
        "shadow": 0,
        "alignment": 2,
        "margin_v": 220,
        "background_opacity": 0.0,
        "animation": "pop",
    },
    "youtube_shorts": {
        "label": "YouTube Shorts",
        "font_name": "Roboto",
        "font_size": 50,
        "bold": 1,
        "primary_colour": "&H00FFFFFF",
        "outline_colour": "&H00000000",
        "back_colour": "&H80000000",
        "outline": 2,
        "shadow": 1,
        "alignment": 2,
        "margin_v": 140,
        "background_opacity": 0.5,
    },
    "karaoke": {
        "label": "Karaoke",
        "font_name": "Arial",
        "font_size": 54,
        "bold": 1,
        "primary_colour": "&H0000FFFF",
        "outline_colour": "&H00000000",
        "back_colour": "&H00000000",
        "outline": 3,
        "shadow": 0,
        "alignment": 2,
        "margin_v": 200,
        "karaoke": True,
    },
    "minimal": {
        "label": "Minimal",
        "font_name": "Helvetica",
        "font_size": 40,
        "bold": 0,
        "primary_colour": "&H00FFFFFF",
        "outline_colour": "&H00000000",
        "back_colour": "&H00000000",
        "outline": 1,
        "shadow": 0,
        "alignment": 2,
        "margin_v": 60,
    },
    "bold": {
        "label": "Bold",
        "font_name": "Impact",
        "font_size": 60,
        "bold": 1,
        "primary_colour": "&H00FFFFFF",
        "outline_colour": "&H00000000",
        "back_colour": "&H00000000",
        "outline": 5,
        "shadow": 0,
        "alignment": 2,
        "margin_v": 160,
    },
    "highlight": {
        "label": "Highlight",
        "font_name": "Arial",
        "font_size": 48,
        "bold": 1,
        "primary_colour": "&H00000000",
        "outline_colour": "&H00000000",
        "back_colour": "&H0000FFFF",
        "outline": 0,
        "shadow": 0,
        "alignment": 2,
        "margin_v": 120,
        "background_opacity": 1.0,
        "border_style": 3,
    },
    "neon": {
        "label": "Neon",
        "font_name": "Arial",
        "font_size": 52,
        "bold": 1,
        "primary_colour": "&H00FF66FF",
        "outline_colour": "&H00FF00AA",
        "back_colour": "&H00000000",
        "outline": 3,
        "shadow": 3,
        "alignment": 2,
        "margin_v": 180,
    },
    "custom": {
        "label": "Custom",
        "font_name": "Arial",
        "font_size": 48,
        "bold": 0,
        "primary_colour": "&H00FFFFFF",
        "outline_colour": "&H00000000",
        "back_colour": "&H64000000",
        "outline": 3,
        "shadow": 0,
        "alignment": 2,
        "margin_v": 80,
    },
}


def list_presets() -> dict[str, Any]:
    return deepcopy(CAPTION_PRESETS)


def resolve_preset(name: str | None, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    base = deepcopy(CAPTION_PRESETS.get(name or "classic") or CAPTION_PRESETS["classic"])
    if overrides:
        base.update(overrides)
    return base


def hex_to_ass_bgr(color: str, alpha: str = "00") -> str:
    """Convert #RRGGBB to ASS &HAABBGGRR."""
    c = color.strip().lstrip("#")
    if len(c) == 6:
        r, g, b = c[0:2], c[2:4], c[4:6]
        return f"&H{alpha}{b}{g}{r}".upper()
    return "&H00FFFFFF"
