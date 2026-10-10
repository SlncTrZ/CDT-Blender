"""Additive Blender L2 motion-infographic MCP tool schemas.

No arbitrary bpy/Python/Geometry Node graphs. All paths must be checked against
workstation allow-roots again by the addon before native mutations.
"""

from __future__ import annotations

from mcp import types

_VEC3 = {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3}
_POINT = {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 3}
_STROKES = {
    "type": "array",
    "minItems": 1,
    "maxItems": 32,
    "items": {"type": "array", "minItems": 2, "maxItems": 256, "items": _POINT},
}
_HEX = {"type": "string", "pattern": "^#[0-9A-Fa-f]{6}$"}
_FRAMES = {"type": "integer", "minimum": 1, "maximum": 100000}


def _tool(name: str, description: str, required: list[str], props: dict) -> types.Tool:
    return types.Tool(
        name=name,
        description=description,
        inputSchema={
            "type": "object",
            "properties": props,
            "required": required,
            "additionalProperties": False,
        },
    )


def get_infographic_tools() -> list[types.Tool]:
    return [
        _tool(
            "import_svg_curves",
            "Import a vetted offline basic SVG as Blender CURVE objects. Rejects active/external content, requires workstation allow-root; scales to optional width.",
            ["filepath", "prefix"],
            {
                "filepath": {"type": "string", "maxLength": 2048},
                "prefix": {"type": "string", "pattern": "^[A-Za-z][A-Za-z0-9_]{0,47}$"},
                "target_width": {"type": "number", "minimum": 0.01, "maximum": 1000},
                "location": _VEC3,
            },
        ),
        _tool(
            "create_grease_strokes",
            "Create bounded Grease Pencil v3 strokes with optional held-frame progressive reveal (Blender 4.5+).",
            ["name", "strokes"],
            {
                "name": {"type": "string", "pattern": "^[A-Za-z][A-Za-z0-9_]{0,63}$"},
                "strokes": _STROKES,
                "color": _HEX,
                "radius": {"type": "number", "minimum": 0.001, "maximum": 3, "default": 0.045},
                "start_frame": {**_FRAMES, "default": 1},
                "end_frame": _FRAMES,
                "steps": {"type": "integer", "minimum": 1, "maximum": 30, "default": 1},
            },
        ),
        _tool(
            "create_filled_grease_tween",
            "Animate closed filled Grease Pencil v3 polygons across held frames. Start/end strokes MUST have identical point counts.",
            ["name", "start_strokes", "end_strokes"],
            {
                "name": {"type": "string", "pattern": "^[A-Za-z][A-Za-z0-9_]{0,63}$"},
                "start_strokes": _STROKES,
                "end_strokes": _STROKES,
                "start_frame": {**_FRAMES, "default": 1},
                "end_frame": {**_FRAMES, "default": 45},
                "steps": {"type": "integer", "minimum": 2, "maximum": 32, "default": 12},
                "fill_color": _HEX,
                "outline_color": _HEX,
                "radius": {"type": "number", "minimum": 0.001, "maximum": 2, "default": 0.03},
                "easing": {
                    "type": "string",
                    "enum": ["LINEAR", "SMOOTHSTEP"],
                    "default": "SMOOTHSTEP",
                },
            },
        ),
        _tool(
            "create_particle_preset",
            "Create a bounded curated Geometry Nodes LINE/RING instancing preset, with ring rotation keyframes.",
            ["name"],
            {
                "name": {"type": "string", "pattern": "^[A-Za-z][A-Za-z0-9_]{0,63}$"},
                "mode": {"type": "string", "enum": ["LINE", "RING"], "default": "LINE"},
                "count": {"type": "integer", "minimum": 2, "maximum": 256, "default": 25},
                "radius": {"type": "number", "minimum": 0.005, "maximum": 5, "default": 0.04},
                "color": _HEX,
                "start": _VEC3,
                "end": _VEC3,
                "ring_radius": {"type": "number", "minimum": 0.1, "maximum": 100, "default": 1.0},
                "frame_start": {**_FRAMES, "default": 1},
                "frame_end": {**_FRAMES, "default": 60},
            },
        ),
        _tool(
            "create_animated_particle_grid",
            "Build animated Geometry Nodes wave grid of up to 512 particles; no custom node injection.",
            ["name"],
            {
                "name": {"type": "string", "pattern": "^[A-Za-z][A-Za-z0-9_]{0,63}$"},
                "rows": {"type": "integer", "minimum": 2, "maximum": 40, "default": 8},
                "columns": {"type": "integer", "minimum": 2, "maximum": 40, "default": 14},
                "spacing": {"type": "number", "minimum": 0.05, "maximum": 10, "default": 0.25},
                "amplitude": {"type": "number", "minimum": 0, "maximum": 5, "default": 0.22},
                "particle_radius": {
                    "type": "number",
                    "minimum": 0.005,
                    "maximum": 1,
                    "default": 0.035,
                },
                "color": _HEX,
                "start_frame": {**_FRAMES, "default": 1},
                "end_frame": {**_FRAMES, "default": 60},
            },
        ),
        _tool(
            "create_unicode_text",
            "Native NFC Latin/Vietnamese multiline TextCurve; font files require allow-roots. Arabic/Indic shaping is NOT supported here.",
            ["name", "text"],
            {
                "name": {"type": "string", "pattern": "^[A-Za-z][A-Za-z0-9_]{0,63}$"},
                "text": {"type": "string", "minLength": 1, "maxLength": 512},
                "size": {"type": "number", "minimum": 0.01, "maximum": 100, "default": 0.5},
                "tracking": {"type": "number", "minimum": 0.1, "maximum": 10, "default": 1},
                "line_spacing": {"type": "number", "minimum": 0.1, "maximum": 10, "default": 1.2},
                "align": {
                    "type": "string",
                    "enum": ["LEFT", "CENTER", "RIGHT", "JUSTIFY"],
                    "default": "LEFT",
                },
                "color": _HEX,
                "location": _VEC3,
                "font_path": {"type": "string", "maxLength": 2048},
            },
        ),
        _tool(
            "create_shaped_text_plane",
            "Place an externally HarfBuzz/RAQM-shaped transparent PNG as an image-backed plane (not editable glyphs). PNG requires workstation allow-root.",
            ["name", "png_path"],
            {
                "name": {"type": "string", "pattern": "^[A-Za-z][A-Za-z0-9_]{0,63}$"},
                "png_path": {"type": "string", "maxLength": 2048},
                "width": {"type": "number", "minimum": 0.05, "maximum": 100, "default": 3.0},
                "location": _VEC3,
            },
        ),
    ]
