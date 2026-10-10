"""Native Blender 4.5+ motion infographic primitives (internal, not public MCP tools).

Provider-facing contracts are gated on CDT_Engineer approval. These functions
operate only on the caller's explicitly selected scene; no arbitrary Python API.
"""

from __future__ import annotations

import math
import unicodedata

import bpy  # type: ignore


def _hex_rgba(value: str) -> tuple[float, float, float, float]:
    if not isinstance(value, str) or len(value) != 7 or value[0] != "#":
        raise ValueError("Expected #RRGGBB")
    try:
        channels = tuple(int(value[i : i + 2], 16) / 255 for i in (1, 3, 5))
    except ValueError as exc:
        raise ValueError("Expected #RRGGBB") from exc
    return (*channels, 1.0)


def _graphemes(text: str) -> list[str]:
    """Conservative combining-mark/ZWJ grouping; not full Unicode UAX #29."""
    result: list[str] = []
    for char in text:
        if result and (
            unicodedata.combining(char)
            or char == "\u200d"
            or result[-1].endswith("\u200d")
            or "\ufe00" <= char <= "\ufe0f"
        ):
            result[-1] += char
        else:
            result.append(char)
    return result


def animate_characters(
    *,
    text: str,
    prefix: str,
    start_frame: int,
    stagger: int = 3,
    duration: int = 12,
    size: float = 0.5,
    tracking: float = 0.36,
    location: tuple[float, float, float] = (0, 0, 0),
    color: str = "#FFFFFF",
    rise: float = 0.28,
) -> list[str]:
    """Create independent glyph objects with staggered slide/scale/opacity.

    Glyph spacing uses explicit tracking (not font kerning). Spaces advance the
    cursor but do not create objects. Existing names are refused atomically.
    """
    if not text or len(text) > 128 or not prefix or len(prefix) > 60:
        raise ValueError("Text must have 1..128 characters and a valid prefix")
    if (
        not isinstance(start_frame, int)
        or not isinstance(stagger, int)
        or not isinstance(duration, int)
        or start_frame < 1
        or stagger < 0
        or duration < 1
    ):
        raise ValueError("Invalid frame range")
    if (
        any(not math.isfinite(v) for v in (size, tracking, rise, *location))
        or size <= 0
        or tracking <= 0
        or rise < 0
    ):
        raise ValueError("Invalid geometry values")
    rgba = _hex_rgba(color)
    glyphs = _graphemes(text)
    names = [f"{prefix}_{i:03d}" for i, glyph in enumerate(glyphs) if not glyph.isspace()]
    if any(bpy.data.objects.get(n) or bpy.data.materials.get(n + "_MAT") for n in names):
        raise ValueError("Glyph object/material name already exists")
    created: list[str] = []
    for i, glyph in enumerate(glyphs):
        if glyph.isspace():
            continue
        name = f"{prefix}_{i:03d}"
        font = bpy.data.curves.new(name + "_FONT", "FONT")
        font.body = glyph
        font.size = size
        obj = bpy.data.objects.new(name, font)
        bpy.context.scene.collection.objects.link(obj)
        mat = bpy.data.materials.new(name + "_MAT")
        mat.use_nodes = True
        mat.diffuse_color = rgba
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        bsdf.inputs["Base Color"].default_value = rgba
        bsdf.inputs["Emission Color"].default_value = rgba
        bsdf.inputs["Emission Strength"].default_value = 1.0
        obj.data.materials.append(mat)
        if hasattr(mat, "surface_render_method"):
            mat.surface_render_method = "DITHERED"
        alpha = bsdf.inputs["Alpha"]
        begin = start_frame + i * stagger
        end = begin + duration
        alpha.default_value = 0.0
        alpha.keyframe_insert(data_path="default_value", frame=begin)
        alpha.default_value = 1.0
        alpha.keyframe_insert(data_path="default_value", frame=end)
        x, y, z = location
        obj.location = (x + i * tracking, y - rise, z)
        obj.scale = (0.8, 0.8, 0.8)
        obj.keyframe_insert(data_path="location", frame=begin)
        obj.keyframe_insert(data_path="scale", frame=begin)
        obj.location = (x + i * tracking, y, z)
        obj.scale = (1, 1, 1)
        obj.keyframe_insert(data_path="location", frame=end)
        obj.keyframe_insert(data_path="scale", frame=end)
        created.append(name)
    return created


def configure_gradient_material(
    name: str,
    *,
    start_color: str,
    end_color: str,
    emission_strength: float = 1.0,
    axis: str = "X",
) -> str:
    """Create a two-stop procedural gradient with emission and a ColorRamp."""
    start, end = _hex_rgba(start_color), _hex_rgba(end_color)
    if not name or bpy.data.materials.get(name):
        raise ValueError("Material name is empty or already exists")
    if (
        axis not in {"X", "Y", "Z"}
        or not math.isfinite(emission_strength)
        or not 0 <= emission_strength <= 100
    ):
        raise ValueError("Invalid gradient axis or emission strength")
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    coords = nodes.new("ShaderNodeTexCoord")
    separate = nodes.new("ShaderNodeSeparateXYZ")
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = start
    ramp.color_ramp.elements[1].color = end
    links.new(coords.outputs["Generated"], separate.inputs["Vector"])
    links.new(separate.outputs[axis], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Emission Color"])
    bsdf.inputs["Emission Strength"].default_value = emission_strength
    return mat.name
