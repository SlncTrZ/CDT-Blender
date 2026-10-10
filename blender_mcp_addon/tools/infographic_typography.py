"""Internal typewriter animation preset for Blender infographic typography."""

from __future__ import annotations

import bpy  # type: ignore

from .infographic_native import _graphemes, animate_characters


def animate_typewriter(
    *,
    text: str,
    prefix: str,
    start_frame: int,
    frames_per_character: int = 3,
    size: float = 0.5,
    tracking: float = 0.02,
    location: tuple[float, float, float] = (0, 0, 0),
    color: str = "#FFFFFF",
) -> dict:
    """Reveal characters discretely in sequence (not a continuous opacity fade).

    Glyph advance uses measured font geometry plus tracking, but does not
    implement pair kerning or complex script shaping. Unicode grapheme grouping
    is conservative, not UAX#29.
    """
    if (
        not isinstance(frames_per_character, int)
        or isinstance(frames_per_character, bool)
        or not 1 <= frames_per_character <= 120
    ):
        raise ValueError("frames_per_character must be 1..120")
    if (
        not isinstance(start_frame, int)
        or isinstance(start_frame, bool)
        or not 1 <= start_frame <= 100000
    ):
        raise ValueError("Invalid start_frame")
    if not isinstance(text, str) or not 0 < len(text) <= 128:
        raise ValueError("Invalid typewriter text")
    names = animate_characters(
        text=text,
        prefix=prefix,
        start_frame=start_frame,
        stagger=frames_per_character,
        duration=1,
        size=size,
        tracking=tracking,
        location=location,
        color=color,
        rise=0,
    )
    # Measure font geometry rather than using a fixed character cell width.
    # Boolean hide_render is evaluated discretely by Blender. Spaces still
    # consume time because glyph index is preserved in the object name.
    bpy.context.view_layer.update()
    cursor = 0.0
    for index, glyph in enumerate(_graphemes(text)):
        if glyph.isspace():
            cursor += size * 0.55
            continue
        name = f"{prefix}_{index:03d}"
        obj = bpy.data.objects[name]
        width = obj.dimensions.x / max(obj.scale.x, 0.001)
        obj.location.x = location[0] + cursor
        begin = start_frame + index * frames_per_character
        obj.keyframe_insert(data_path="location", frame=begin)
        obj.keyframe_insert(data_path="location", frame=begin + 1)
        cursor += width + tracking
        reveal = start_frame + index * frames_per_character + 1
        obj.hide_render = True
        obj.keyframe_insert(data_path="hide_render", frame=start_frame)
        obj.keyframe_insert(data_path="hide_render", frame=max(start_frame, reveal - 1))
        obj.hide_render = False
        obj.keyframe_insert(data_path="hide_render", frame=reveal)
    return {
        "objects": names,
        "graphemes": len(_graphemes(text)),
        "start": start_frame,
        "stagger": frames_per_character,
    }
