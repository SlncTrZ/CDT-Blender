"""Bounded Unicode typography for Blender infographic layouts.

Supports NFC Vietnamese and broadly Latin-script text, explicit multiline
layout and optional allowed-root font. Complex shaping is refused, not guessed.
"""

from __future__ import annotations

import os
import re
import unicodedata

import bpy  # type: ignore

from .infographic_native import _graphemes, _hex_rgba

_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,63}\Z")
_COMPLEX_SCRIPT_RANGES = (
    (0x0590, 0x08FF),  # Hebrew, Arabic, Syriac and neighbors
    (0x0900, 0x109F),  # Indic, Burmese and related scripts
    (0x1780, 0x17FF),  # Khmer
    (0x0E00, 0x0EFF),  # Thai and Lao
    (0xFB1D, 0xFEFF),  # presentation forms; Arabic shaping
)


def validate_unicode_text(text: str) -> dict:
    """Normalize to NFC; reject unsupported shaping and control codepoints."""
    if not isinstance(text, str) or not 1 <= len(text) <= 512 or not text.strip():
        raise ValueError("Unicode text must contain 1..512 characters")
    normalized = unicodedata.normalize("NFC", text)
    for ch in normalized:
        cp = ord(ch)
        if ch not in {"\n", "\t"} and unicodedata.category(ch) in {"Cc", "Cs", "Cf"}:
            raise ValueError("Unicode control or formatting codepoint refused")
        if any(low <= cp <= high for low, high in _COMPLEX_SCRIPT_RANGES):
            raise ValueError("Complex-script shaping requires a verified HarfBuzz pipeline")
        if ch == "\u200d" or ch == "\u200c":
            raise ValueError("ZWJ/ZWNJ shaping requires a verified text engine")
    return {
        "text": normalized,
        "codepoints": len(normalized),
        "grapheme_clusters_estimate": len(_graphemes(normalized)),
        "line_count": normalized.count("\n") + 1,
        "normalized_nfc": normalized == text,
    }


def create_unicode_text(
    name: str,
    *,
    text: str,
    size: float = 0.5,
    tracking: float = 1,
    line_spacing: float = 1.2,
    align: str = "LEFT",
    color: str = "#FFFFFF",
    location: tuple[float, float, float] = (0, 0, 0),
    font_path: str | None = None,
    allow_roots: list[str] | tuple[str, ...] = (),
) -> dict:
    """Create one native TextCurve with owned material and optional safe font.

    For complex shaping-dependent scripts fail closed instead of rendering
    misleading glyph order. Glyph estimate is not full UAX #29.
    """
    info = validate_unicode_text(text)
    if not isinstance(name, str) or not _NAME.fullmatch(name):
        raise ValueError("Invalid text object name")
    for field, value, low, high in (
        ("size", size, 0.01, 100),
        ("tracking", tracking, 0.1, 10),
        ("line_spacing", line_spacing, 0.1, 10),
    ):
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not low <= value <= high
        ):
            raise ValueError(f"Invalid {field}")
    if align not in {"LEFT", "CENTER", "RIGHT", "JUSTIFY"}:
        raise ValueError("Unsupported text alignment")
    if (
        not isinstance(location, (list, tuple))
        or len(location) != 3
        or any(
            isinstance(v, bool) or not isinstance(v, (int, float)) or not -10000 <= v <= 10000
            for v in location
        )
    ):
        raise ValueError("Invalid text location")
    rgba = _hex_rgba(color)
    chosen_font = None
    if font_path is not None:
        if not isinstance(font_path, str) or not font_path.lower().endswith((".ttf", ".otf")):
            raise ValueError("TrueType/OpenType font file required")
        from ..utils import require_allowed

        checked_path = require_allowed(font_path, allow_roots)
        if (
            not os.path.isfile(checked_path)
            or not 1024 <= os.path.getsize(checked_path) <= 16 * 1024 * 1024
        ):
            raise ValueError("Font missing or outside permitted size range")
        chosen_font = checked_path
    if (
        bpy.data.objects.get(name)
        or bpy.data.curves.get(name + "_FONT")
        or bpy.data.materials.get(name + "_MAT")
    ):
        raise ValueError("Typography object name collision")
    if chosen_font is not None:
        font = bpy.data.fonts.load(chosen_font, check_existing=True)
    else:
        font = None
    curve = bpy.data.curves.new(name + "_FONT", "FONT")
    curve.body = info["text"]
    curve.size = size
    curve.align_x = align
    curve.space_character = tracking
    curve.space_line = line_spacing
    if font:
        curve.font = font
    obj = bpy.data.objects.new(name, curve)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = location
    material = bpy.data.materials.new(name + "_MAT")
    material.use_nodes = True
    material.diffuse_color = rgba
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Emission Color"].default_value = rgba
    bsdf.inputs["Emission Strength"].default_value = 1.0
    curve.materials.append(material)
    return {"object": name, "font": font.name if font else "Blender Bfont", **info}
