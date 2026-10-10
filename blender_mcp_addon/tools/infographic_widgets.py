"""Deterministic bounded native 2D chart primitives for isolated Blender scenes."""

from __future__ import annotations

import math

import bpy  # type: ignore

from .infographic_native import _hex_rgba


def _check_float(value: object, *, low: float, high: float, label: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not low <= value <= high
    ):
        raise ValueError(f"Invalid {label}")
    return float(value)


def _material(name: str, rgba: tuple[float, float, float, float], emission: float):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = rgba
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Emission Color"].default_value = rgba
    bsdf.inputs["Emission Strength"].default_value = emission
    return mat


def create_bar_chart(
    *,
    prefix: str,
    values: list[float],
    colors: list[str],
    origin: tuple[float, float, float] = (0, 0, 0),
    width: float = 0.4,
    spacing: float = 0.2,
    max_height: float = 2.0,
    start_frame: int = 1,
    duration: int = 25,
    stagger: int = 4,
) -> list[str]:
    """Build 1..24 animated vertical bars normalized to largest data value.

    Input validation and name-collision preflight occur before creating objects.
    """
    if not isinstance(prefix, str) or not 0 < len(prefix) <= 60:
        raise ValueError("Invalid prefix")
    if (
        not isinstance(values, list)
        or not 1 <= len(values) <= 24
        or not isinstance(colors, list)
        or len(colors) != len(values)
    ):
        raise ValueError("Require 1..24 values with matching colors")
    vals = [_check_float(v, low=0, high=1e9, label="bar value") for v in values]
    if max(vals) <= 0:
        raise ValueError("At least one bar must be positive")
    rgba = [_hex_rgba(v) for v in colors]
    if len(origin) != 3:
        raise ValueError("origin requires 3 coordinates")
    for val in origin:
        _check_float(val, low=-10000, high=10000, label="origin")
    for name, val, lo, hi in (
        ("width", width, 0.01, 100),
        ("spacing", spacing, 0, 100),
        ("max_height", max_height, 0.01, 100),
    ):
        _check_float(val, low=lo, high=hi, label=name)
    if (
        not isinstance(start_frame, int)
        or isinstance(start_frame, bool)
        or not 1 <= start_frame <= 100000
        or not isinstance(duration, int)
        or not 1 <= duration <= 10000
        or not isinstance(stagger, int)
        or not 0 <= stagger <= 10000
    ):
        raise ValueError("Invalid frame parameters")
    names = [f"{prefix}_BAR_{i:02d}" for i in range(len(vals))]
    if any(
        bpy.data.objects.get(n)
        or bpy.data.materials.get(n + "_MAT")
        or bpy.data.meshes.get(n + "_MESH")
        for n in names
    ):
        raise ValueError("Chart object/material name collision")
    result = []
    for i, (value, color) in enumerate(zip(vals, rgba, strict=True)):
        name = names[i]
        mesh = bpy.data.meshes.new(name + "_MESH")
        # Mesh is a unit square in the XY plane; scale and location are animated.
        mesh.from_pydata([(-0.5, 0, 0), (0.5, 0, 0), (0.5, 1, 0), (-0.5, 1, 0)], [], [(0, 1, 2, 3)])
        mesh.update()
        obj = bpy.data.objects.new(name, mesh)
        bpy.context.scene.collection.objects.link(obj)
        mat = _material(name + "_MAT", color, 1.0)
        mesh.materials.append(mat)
        height = max_height * value / max(vals)
        x = origin[0] + i * (width + spacing)
        obj.location = (x, origin[1], origin[2])
        begin = start_frame + i * stagger
        obj.scale = (width, 0.001, 1)
        obj.keyframe_insert(data_path="scale", frame=begin)
        obj.scale = (width, max(height, 0.001), 1)
        obj.keyframe_insert(data_path="scale", frame=begin + duration)
        result.append(name)
    return result


def create_progress_arc(
    *,
    name: str,
    progress: float,
    color: str = "#00DFFF",
    radius: float = 1,
    thickness: float = 0.04,
    start_frame: int = 1,
    end_frame: int = 40,
    location: tuple[float, float, float] = (0, 0, 0),
) -> str:
    """Create a smooth circular progress curve animated with bevel_factor_end."""
    if not isinstance(name, str) or not 0 < len(name) <= 80:
        raise ValueError("Invalid name")
    progress = _check_float(progress, low=0, high=1, label="progress")
    radius = _check_float(radius, low=0.01, high=100, label="radius")
    thickness = _check_float(thickness, low=0.001, high=10, label="thickness")
    rgba = _hex_rgba(color)
    if len(location) != 3:
        raise ValueError("Invalid location")
    for val in location:
        _check_float(val, low=-10000, high=10000, label="location")
    if (
        not isinstance(start_frame, int)
        or not isinstance(end_frame, int)
        or not 1 <= start_frame < end_frame <= 100000
    ):
        raise ValueError("Invalid animation interval")
    if (
        bpy.data.objects.get(name)
        or bpy.data.curves.get(name + "_CURVE")
        or bpy.data.materials.get(name + "_MAT")
    ):
        raise ValueError("Progress arc name collision")
    curve = bpy.data.curves.new(name + "_CURVE", "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 16
    curve.bevel_depth = thickness
    curve.bevel_resolution = 3
    spline = curve.splines.new("POLY")
    spline.points.add(128)
    for i, point in enumerate(spline.points):
        angle = math.pi / 2 - 2 * math.pi * i / 128
        point.co = (radius * math.cos(angle), radius * math.sin(angle), 0, 1)
    obj = bpy.data.objects.new(name, curve)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = location
    curve.materials.append(_material(name + "_MAT", rgba, 1.5))
    curve.bevel_factor_end = 0
    curve.keyframe_insert(data_path="bevel_factor_end", frame=start_frame)
    curve.bevel_factor_end = progress
    curve.keyframe_insert(data_path="bevel_factor_end", frame=end_frame)
    return obj.name
