"""Reusable caption style presets (system + user custom)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import uuid4

# ASS PlayRes used by the exporter (must match Flutter preview aspect math)
PLAY_RES_X = 1080
PLAY_RES_Y = 1920

# Default editable style schema — presets are starting points, not locks.
DEFAULT_STYLE: dict[str, Any] = {
    "label": "Custom",
    "preset": "custom",
    "system": False,
    "font_name": "Arial",
    "font_size": 48,
    "font_weight": 400,  # 400 regular … 700 bold (maps to ASS Bold)
    "bold": 0,
    "italic": 0,
    "letter_spacing": 0.0,
    "line_spacing": 1.0,
    "primary_colour": "&H00FFFFFF",
    "outline_colour": "&H00000000",
    "back_colour": "&H64000000",
    "text_opacity": 1.0,
    "background_opacity": 0.4,
    "outline": 3,
    "shadow": 0,
    "border_style": 1,  # 1 outline+shadow, 3 opaque box
    "alignment": 2,  # ASS numpad: 1–3 bottom, 4–6 mid, 7–9 top
    "margin_l": 40,
    "margin_r": 40,
    "margin_v": 80,
    "padding": 8,
    "max_width": 1000,
    "max_lines": 3,
    "corner_radius": 0,
    # Absolute position in PlayRes coords; null → alignment/margins
    "pos_x": None,
    "pos_y": None,
    "animation_in": "none",
    "animation_out": "none",
    "animation_duration": 0.25,
    "karaoke": False,
}

# ASS colours are &HAABBGGRR
CAPTION_PRESETS: dict[str, dict[str, Any]] = {
    "classic": {
        "label": "Classic",
        "font_name": "Arial",
        "font_size": 48,
        "font_weight": 400,
        "bold": 0,
        "primary_colour": "&H00FFFFFF",
        "outline_colour": "&H00000000",
        "back_colour": "&H64000000",
        "outline": 3,
        "shadow": 0,
        "alignment": 2,
        "margin_v": 80,
        "background_opacity": 0.4,
        "text_opacity": 1.0,
    },
    "modern": {
        "label": "Modern",
        "font_name": "Montserrat",
        "font_size": 52,
        "font_weight": 700,
        "bold": 1,
        "primary_colour": "&H00FFFFFF",
        "outline_colour": "&H00222222",
        "back_colour": "&H00000000",
        "outline": 0,
        "shadow": 2,
        "alignment": 2,
        "margin_v": 100,
        "background_opacity": 0.0,
        "text_opacity": 1.0,
    },
    "tiktok": {
        "label": "TikTok",
        "font_name": "Arial Black",
        "font_size": 56,
        "font_weight": 900,
        "bold": 1,
        "primary_colour": "&H00FFFFFF",
        "outline_colour": "&H00000000",
        "back_colour": "&H00000000",
        "outline": 4,
        "shadow": 0,
        "alignment": 2,
        "margin_v": 220,
        "background_opacity": 0.0,
        "animation_in": "pop",
        "text_opacity": 1.0,
    },
    "youtube_shorts": {
        "label": "YouTube Shorts",
        "font_name": "Roboto",
        "font_size": 50,
        "font_weight": 700,
        "bold": 1,
        "primary_colour": "&H00FFFFFF",
        "outline_colour": "&H00000000",
        "back_colour": "&H80000000",
        "outline": 2,
        "shadow": 1,
        "alignment": 2,
        "margin_v": 140,
        "background_opacity": 0.5,
        "border_style": 3,
        "text_opacity": 1.0,
    },
    "karaoke": {
        "label": "Karaoke",
        "font_name": "Arial",
        "font_size": 54,
        "font_weight": 700,
        "bold": 1,
        "primary_colour": "&H0000FFFF",
        "outline_colour": "&H00000000",
        "back_colour": "&H00000000",
        "outline": 3,
        "shadow": 0,
        "alignment": 2,
        "margin_v": 200,
        "karaoke": True,
        "text_opacity": 1.0,
    },
    "minimal": {
        "label": "Minimal",
        "font_name": "Helvetica",
        "font_size": 40,
        "font_weight": 400,
        "bold": 0,
        "primary_colour": "&H00FFFFFF",
        "outline_colour": "&H00000000",
        "back_colour": "&H00000000",
        "outline": 1,
        "shadow": 0,
        "alignment": 2,
        "margin_v": 60,
        "background_opacity": 0.0,
        "text_opacity": 1.0,
    },
    "bold": {
        "label": "Bold",
        "font_name": "Impact",
        "font_size": 60,
        "font_weight": 900,
        "bold": 1,
        "primary_colour": "&H00FFFFFF",
        "outline_colour": "&H00000000",
        "back_colour": "&H00000000",
        "outline": 5,
        "shadow": 0,
        "alignment": 2,
        "margin_v": 160,
        "text_opacity": 1.0,
    },
    "highlight": {
        "label": "Highlight",
        "font_name": "Arial",
        "font_size": 48,
        "font_weight": 700,
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
        "text_opacity": 1.0,
    },
    "neon": {
        "label": "Neon",
        "font_name": "Arial",
        "font_size": 52,
        "font_weight": 700,
        "bold": 1,
        "primary_colour": "&H00FF66FF",
        "outline_colour": "&H00FF00AA",
        "back_colour": "&H00000000",
        "outline": 3,
        "shadow": 3,
        "alignment": 2,
        "margin_v": 180,
        "text_opacity": 1.0,
    },
    "custom": {
        "label": "Custom",
        "font_name": "Arial",
        "font_size": 48,
        "font_weight": 400,
        "bold": 0,
        "primary_colour": "&H00FFFFFF",
        "outline_colour": "&H00000000",
        "back_colour": "&H64000000",
        "outline": 3,
        "shadow": 0,
        "alignment": 2,
        "margin_v": 80,
        "background_opacity": 0.4,
        "text_opacity": 1.0,
    },
}

CUSTOM_PRESETS_KEY = "caption_presets_custom"


def normalize_style(style: dict[str, Any] | None) -> dict[str, Any]:
    """Merge unknown/partial style dicts onto the editable schema."""
    out = deepcopy(DEFAULT_STYLE)
    if not style:
        return out
    for key, value in style.items():
        if key == "source":
            out["source"] = value
            continue
        out[key] = value
    # Keep bold in sync with font_weight when weight provided
    if "font_weight" in style and "bold" not in style:
        out["bold"] = 1 if int(out.get("font_weight") or 400) >= 600 else 0
    elif out.get("bold") and not style.get("font_weight"):
        out["font_weight"] = 700
    # Clamp opacities
    out["text_opacity"] = max(0.0, min(1.0, float(out.get("text_opacity", 1.0))))
    out["background_opacity"] = max(0.0, min(1.0, float(out.get("background_opacity", 0.0))))
    out["font_size"] = max(8, int(out.get("font_size") or 48))
    # Position: accept normalized coords
    if out.get("pos_x_norm") is not None and out.get("pos_x") is None:
        out["pos_x"] = float(out["pos_x_norm"]) * PLAY_RES_X
    if out.get("pos_y_norm") is not None and out.get("pos_y") is None:
        out["pos_y"] = float(out["pos_y_norm"]) * PLAY_RES_Y
    return out


def list_system_presets() -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, preset in CAPTION_PRESETS.items():
        style = normalize_style(preset)
        style["preset"] = key
        style["system"] = True
        style["id"] = key
        result[key] = style
    return result


def list_presets(custom: dict[str, Any] | None = None) -> dict[str, Any]:
    merged = list_system_presets()
    for key, preset in (custom or {}).items():
        style = normalize_style(preset)
        style["preset"] = key
        style["system"] = False
        style["id"] = key
        merged[key] = style
    return merged


def resolve_preset(
    name: str | None,
    overrides: dict[str, Any] | None = None,
    *,
    custom: dict[str, Any] | None = None,
) -> dict[str, Any]:
    all_presets = list_presets(custom)
    base = deepcopy(all_presets.get(name or "classic") or all_presets["classic"])
    if overrides:
        base.update(overrides)
    return normalize_style(base)


def hex_to_ass_bgr(color: str, alpha: str = "00") -> str:
    """Convert #RRGGBB to ASS &HAABBGGRR."""
    c = color.strip().lstrip("#")
    if len(c) == 6:
        r, g, b = c[0:2], c[2:4], c[4:6]
        return f"&H{alpha}{b}{g}{r}".upper()
    if len(c) == 8:
        # AARRGGBB → ASS AABBGGRR
        a, r, g, b = c[0:2], c[2:4], c[4:6], c[6:8]
        return f"&H{a}{b}{g}{r}".upper()
    return "&H00FFFFFF"


def opacity_to_ass_alpha(opacity: float) -> str:
    """Flutter/CSS opacity 1=opaque → ASS alpha 00; 0=transparent → FF."""
    alpha = int(round((1.0 - max(0.0, min(1.0, opacity))) * 255))
    return f"{alpha:02X}"


def apply_text_opacity(primary_colour: str, text_opacity: float) -> str:
    colour = primary_colour.strip()
    if colour.startswith("&H") and len(colour) >= 10:
        body = colour[2:]
        if len(body) == 8:
            body = body[2:]
        return f"&H{opacity_to_ass_alpha(text_opacity)}{body[-6:]}".upper()
    return hex_to_ass_bgr(colour, opacity_to_ass_alpha(text_opacity))


def apply_back_opacity(back_colour: str, background_opacity: float) -> str:
    colour = back_colour.strip()
    if colour.startswith("&H") and len(colour) >= 10:
        body = colour[2:]
        if len(body) == 8:
            body = body[2:]
        return f"&H{opacity_to_ass_alpha(background_opacity)}{body[-6:]}".upper()
    return hex_to_ass_bgr(colour, opacity_to_ass_alpha(background_opacity))


def new_custom_preset_id(label: str) -> str:
    slug = "".join(ch.lower() if ch.isalnum() else "_" for ch in label).strip("_")
    slug = "_".join(part for part in slug.split("_") if part) or "custom"
    return f"user_{slug}_{uuid4().hex[:8]}"
