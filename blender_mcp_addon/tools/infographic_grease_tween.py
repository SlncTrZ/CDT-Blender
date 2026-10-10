"""Internal Grease Pencil v3 filled polygon and point-correspondence tween.

Each frame is a fully materialized held drawing. This is NOT native GP edit
mode interpolation: no topology changes, no extrapolation, no tween of fill
holes or multi-layer masks. Inputs are validated before native writes.
"""

from __future__ import annotations

import math
import re

import bpy  # type: ignore

from .infographic_grease import _stroke_points
from .infographic_native import _hex_rgba


def _validate_morph(start_strokes: list, end_strokes: list, frames: int) -> tuple:
    source = _stroke_points(start_strokes)
    target = _stroke_points(end_strokes)
    if len(source) != len(target) or any(
        len(a) != len(b) for a, b in zip(source, target, strict=True)
    ):
        raise ValueError("Tween requires identical stroke count and point topology")
    if any(len(s) < 3 for s in source):
        raise ValueError("Filled polygon tween requires at least three points per stroke")
    if isinstance(frames, bool) or not isinstance(frames, int) or not 2 <= frames <= 32:
        raise ValueError("Tween frame count must be 2..32")
    return source, target


def create_filled_grease_tween(
    name: str,
    *,
    start_strokes: list,
    end_strokes: list,
    start_frame: int = 1,
    end_frame: int = 45,
    steps: int = 12,
    fill_color: str = "#42BDFB",
    outline_color: str = "#A0EEFF",
    radius: float = 0.03,
    easing: str = "SMOOTHSTEP",
) -> dict:
    """Interpolate same-topology closed GPv3 polygons over bounded drawing frames."""
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", name):
        raise ValueError("Invalid Grease Pencil object name")
    source, target = _validate_morph(start_strokes, end_strokes, steps)
    fill = _hex_rgba(fill_color)
    outline = _hex_rgba(outline_color)
    if easing not in {"LINEAR", "SMOOTHSTEP"}:
        raise ValueError("Unsupported GP easing")
    if (
        isinstance(radius, bool)
        or not isinstance(radius, (int, float))
        or not math.isfinite(radius)
        or not 0.001 <= radius <= 2
    ):
        raise ValueError("Invalid GP outline radius")
    if any(isinstance(f, bool) or not isinstance(f, int) for f in (start_frame, end_frame)):
        raise ValueError("Invalid GP frame type")
    if not 1 <= start_frame < end_frame <= 100000 or end_frame - start_frame < steps - 1:
        raise ValueError("Frame interval too short for tween steps")
    if not hasattr(bpy.data, "grease_pencils_v3"):
        raise ValueError("Blender Grease Pencil v3 required")
    if any(
        (
            bpy.data.objects.get(name),
            bpy.data.grease_pencils_v3.get(name + "_GP"),
            bpy.data.materials.get(name + "_MAT"),
        )
    ):
        raise ValueError("Grease Pencil tween name is already in use")

    gp = bpy.data.grease_pencils_v3.new(name + "_GP")
    obj = bpy.data.objects.new(name, gp)
    bpy.context.scene.collection.objects.link(obj)
    mat = bpy.data.materials.new(name + "_MAT")
    bpy.data.materials.create_gpencil_data(mat)
    mat.grease_pencil.show_stroke = True
    mat.grease_pencil.color = outline
    mat.grease_pencil.show_fill = True
    mat.grease_pencil.fill_color = fill
    gp.materials.append(mat)
    layer = gp.layers.new("FilledTween", set_active=True)
    frames = [start_frame + (end_frame - start_frame) * i // (steps - 1) for i in range(steps)]
    for idx, frame_no in enumerate(frames):
        t = idx / (steps - 1)
        if easing == "SMOOTHSTEP":
            t = t * t * (3 - 2 * t)
        drawing = layer.frames.new(frame_no).drawing
        drawing.add_strokes([len(stroke) for stroke in source])
        for stroke, start_pts, end_pts in zip(drawing.strokes, source, target, strict=True):
            stroke.cyclic = True
            stroke.material_index = 0
            for point, a, b in zip(stroke.points, start_pts, end_pts, strict=True):
                point.position = tuple((1 - t) * a[axis] + t * b[axis] for axis in range(3))
                point.radius = radius
                point.opacity = 1.0
    return {
        "object": obj.name,
        "object_type": obj.type,
        "frames": frames,
        "strokes": len(source),
        "filled": True,
        "easing": easing,
    }
