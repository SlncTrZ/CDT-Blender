"""Blender 4.5 Grease Pencil v3 stroke and held-frame reveal primitives.

Internal provider implementation. Refuses legacy GP types; does not mutate any
existing Grease Pencil objects or animation tracks.
"""

from __future__ import annotations

import math
import re

import bpy  # type: ignore

from .infographic_native import _hex_rgba


def _stroke_points(strokes: list) -> list[list[tuple[float, float, float]]]:
    if not isinstance(strokes, list) or not 1 <= len(strokes) <= 32:
        raise ValueError("Require 1..32 strokes")
    validated = []
    total = 0
    for points in strokes:
        if not isinstance(points, list) or not 2 <= len(points) <= 256:
            raise ValueError("Stroke must have 2..256 points")
        coords = []
        for point in points:
            if not isinstance(point, (list, tuple)) or len(point) not in (2, 3):
                raise ValueError("Stroke point must be XY or XYZ")
            if any(
                isinstance(n, bool)
                or not isinstance(n, (int, float))
                or not math.isfinite(n)
                or abs(n) > 10000
                for n in point
            ):
                raise ValueError("Stroke point must have bounded finite coordinates")
            coords.append(
                (float(point[0]), float(point[1]), float(point[2]) if len(point) == 3 else 0.0)
            )
        validated.append(coords)
        total += len(coords)
    if total > 4096:
        raise ValueError("Stroke point budget exceeded")
    return validated


def create_grease_strokes(
    name: str,
    *,
    strokes: list,
    color: str = "#5CEBFF",
    radius: float = 0.045,
    start_frame: int = 1,
    end_frame: int | None = None,
    steps: int = 1,
) -> dict:
    """Create GPv3 object with strokes; optionally reveal across held frames.

    One step creates one drawing at start_frame; 2..30 create progressive
    drawings from start_frame to end_frame. All drawings use same material.
    """
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", name):
        raise ValueError("Invalid GP object name")
    validated = _stroke_points(strokes)
    rgba = _hex_rgba(color)
    if (
        isinstance(radius, bool)
        or not isinstance(radius, (int, float))
        or not math.isfinite(radius)
        or not 0.001 <= radius <= 3
    ):
        raise ValueError("Invalid GP stroke radius")
    if (
        isinstance(start_frame, bool)
        or not isinstance(start_frame, int)
        or not 1 <= start_frame <= 100000
    ):
        raise ValueError("Invalid GP start_frame")
    if isinstance(steps, bool) or not isinstance(steps, int) or not 1 <= steps <= 30:
        raise ValueError("GP steps must be 1..30")
    if steps > 1:
        if (
            isinstance(end_frame, bool)
            or not isinstance(end_frame, int)
            or not start_frame + steps - 1 <= end_frame <= 100000
        ):
            raise ValueError("GP end_frame insufficient for requested steps")
    elif end_frame is not None:
        raise ValueError("end_frame requires steps > 1")
    if not hasattr(bpy.data, "grease_pencils_v3"):
        raise ValueError("Requires Blender Grease Pencil v3")
    if (
        bpy.data.objects.get(name)
        or bpy.data.grease_pencils_v3.get(name + "_GP")
        or bpy.data.materials.get(name + "_MAT")
    ):
        raise ValueError("Grease Pencil name already in use")

    gp = bpy.data.grease_pencils_v3.new(name + "_GP")
    obj = bpy.data.objects.new(name, gp)
    bpy.context.scene.collection.objects.link(obj)
    mat = bpy.data.materials.new(name + "_MAT")
    bpy.data.materials.create_gpencil_data(mat)
    mat.grease_pencil.show_stroke = True
    mat.grease_pencil.color = rgba
    gp.materials.append(mat)
    layer = gp.layers.new("Infographic", set_active=True)
    total_points = sum(len(points) for points in validated)
    frame_numbers = (
        [start_frame + ((end_frame - start_frame) * i // (steps - 1)) for i in range(steps)]
        if steps > 1
        else [start_frame]
    )
    for index, frame_no in enumerate(frame_numbers):
        drawing = layer.frames.new(frame_no).drawing
        budget = max(2, math.ceil(total_points * (index + 1) / steps))
        fragments = []
        for points in validated:
            if budget < 2:
                break
            count = min(len(points), budget)
            if count >= 2:
                fragments.append(points[:count])
                budget -= count
        drawing.add_strokes([len(points) for points in fragments])
        for stroke, points in zip(drawing.strokes, fragments, strict=True):
            stroke.material_index = 0
            for point, xyz in zip(stroke.points, points, strict=True):
                point.position = xyz
                point.radius = radius
                point.opacity = 1.0
    return {
        "object": obj.name,
        "object_type": obj.type,
        "frames": frame_numbers,
        "strokes": len(validated),
        "points": total_points,
    }
