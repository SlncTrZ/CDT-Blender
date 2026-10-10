"""Bounded native 2D motion primitives; internal until CDT_Engineer contract pin.

No dynamic RNA evaluation, arbitrary Python, user-scene opening, or file writes.
"""

from __future__ import annotations

import math
import re

import bpy  # type: ignore

from .infographic_native import _hex_rgba


def _finite(value: object, low: float, high: float, field: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not low <= value <= high
    ):
        raise ValueError(f"{field} must be finite and between {low} and {high}")
    return float(value)


def _tokens(text: str, mode: str) -> list[str]:
    if mode == "word":
        return re.findall(r"\S+|\s+", text)
    if mode == "line":
        return text.splitlines(keepends=True)
    raise ValueError("mode must be word or line")


def animate_text_groups(
    *,
    text: str,
    prefix: str,
    mode: str,
    start_frame: int,
    stagger: int = 5,
    duration: int = 12,
    size: float = 0.5,
    location: tuple[float, float, float] = (0, 0, 0),
    color: str = "#FFFFFF",
    rise: float = 0.25,
    line_height: float = 0.8,
) -> list[str]:
    """Animate words or lines as separate objects, preserving original whitespace.

    Uses font object dimensions for word spacing. Not full complex-script shaping.
    """
    if (
        not isinstance(text, str)
        or not 0 < len(text) <= 256
        or not isinstance(prefix, str)
        or not 0 < len(prefix) <= 60
    ):
        raise ValueError("Invalid text/prefix length")
    if (
        not isinstance(start_frame, int)
        or start_frame < 1
        or not isinstance(stagger, int)
        or not 0 <= stagger <= 120
        or not isinstance(duration, int)
        or not 1 <= duration <= 600
    ):
        raise ValueError("Invalid animation frames")
    for field, val, low, high in (
        ("size", size, 0.01, 20),
        ("rise", rise, 0, 20),
        ("line_height", line_height, 0.01, 20),
    ):
        _finite(val, low, high, field)
    if len(location) != 3:
        raise ValueError("location must have 3 elements")
    for val in location:
        _finite(val, -10000, 10000, "location")
    rgba = _hex_rgba(color)
    tokens = _tokens(text, mode)
    parts = [(i, t.strip("\r\n")) for i, t in enumerate(tokens) if t.strip()]
    if not parts or len(parts) > 128:
        raise ValueError("No visible tokens or too many tokens")
    names = [f"{prefix}_{i:03d}" for i, _ in parts]
    if any(
        bpy.data.objects.get(n)
        or bpy.data.materials.get(n + "_MAT")
        or bpy.data.curves.get(n + "_FONT")
        for n in names
    ):
        raise ValueError("Text group name collision")
    created: list[str] = []
    cursor_x, cursor_y, z = location
    visible_index = 0
    for i, token in enumerate(tokens):
        if mode == "line" and not token.strip():
            cursor_y -= line_height
            continue
        if mode == "word" and not token.strip():
            cursor_x += len(token) * size * 0.3
            continue
        name = f"{prefix}_{i:03d}"
        font = bpy.data.curves.new(name + "_FONT", "FONT")
        font.body = token.rstrip("\r\n")
        font.size = size
        obj = bpy.data.objects.new(name, font)
        bpy.context.scene.collection.objects.link(obj)
        mat = bpy.data.materials.new(name + "_MAT")
        mat.use_nodes = True
        mat.diffuse_color = rgba
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        bsdf.inputs["Base Color"].default_value = rgba
        bsdf.inputs["Emission Color"].default_value = rgba
        bsdf.inputs["Emission Strength"].default_value = 1
        if hasattr(mat, "surface_render_method"):
            mat.surface_render_method = "DITHERED"
        font.materials.append(mat)
        begin = start_frame + visible_index * stagger
        end = begin + duration
        alpha = bsdf.inputs["Alpha"]
        alpha.default_value = 0
        alpha.keyframe_insert(data_path="default_value", frame=begin)
        alpha.default_value = 1
        alpha.keyframe_insert(data_path="default_value", frame=end)
        obj.location = (cursor_x, cursor_y - rise, z)
        obj.keyframe_insert(data_path="location", frame=begin)
        obj.location = (cursor_x, cursor_y, z)
        obj.keyframe_insert(data_path="location", frame=end)
        created.append(name)
        visible_index += 1
        if mode == "word":
            bpy.context.view_layer.update()
            cursor_x += obj.dimensions.x + size * 0.07
        else:
            cursor_y -= line_height
    return created


def gradient_with_stops(
    name: str,
    *,
    stops: list[dict],
    axis: str = "X",
    emission_strength: float = 1,
    interpolation: str = "LINEAR",
) -> str:
    """Make an emission gradient with 2..8 ordered color stops."""
    if not isinstance(name, str) or not 0 < len(name) <= 80 or bpy.data.materials.get(name):
        raise ValueError("Material name invalid or in use")
    if axis not in {"X", "Y", "Z"} or interpolation not in {
        "LINEAR",
        "EASE",
        "CONSTANT",
        "B_SPLINE",
        "CARDINAL",
    }:
        raise ValueError("Unsupported axis or interpolation")
    _finite(emission_strength, 0, 100, "emission_strength")
    if not isinstance(stops, list) or not 2 <= len(stops) <= 8:
        raise ValueError("Require 2..8 stops")
    validated = []
    for stop in stops:
        if not isinstance(stop, dict) or set(stop) != {"position", "color"}:
            raise ValueError("Each stop requires position and color")
        validated.append((_finite(stop["position"], 0, 1, "position"), _hex_rgba(stop["color"])))
    if (
        any(b[0] <= a[0] for a, b in zip(validated, validated[1:], strict=False))
        or validated[0][0] != 0
        or validated[-1][0] != 1
    ):
        raise ValueError("Stops must be strictly increasing, from 0 to 1")
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    coord = nodes.new("ShaderNodeTexCoord")
    separate = nodes.new("ShaderNodeSeparateXYZ")
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = interpolation
    elements = ramp.color_ramp.elements
    elements[0].position, elements[0].color = validated[0]
    elements[1].position, elements[1].color = validated[-1]
    for pos, rgba in validated[1:-1]:
        elements.new(pos).color = rgba
    links.new(coord.outputs["Generated"], separate.inputs["Vector"])
    links.new(separate.outputs[axis], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Emission Color"])
    bsdf.inputs["Emission Strength"].default_value = emission_strength
    return mat.name


def animate_emission(material_name: str, *, frames: list[dict]) -> int:
    """Animate a material's emission strength, with validation before mutation."""
    mat = bpy.data.materials.get(material_name)
    if not mat or not mat.use_nodes or not mat.node_tree.nodes.get("Principled BSDF"):
        raise ValueError("Existing node-based Principled material required")
    if not isinstance(frames, list) or not 2 <= len(frames) <= 64:
        raise ValueError("Require 2..64 keyframes")
    validated = []
    for point in frames:
        if not isinstance(point, dict) or set(point) != {"frame", "strength"}:
            raise ValueError("Each keyframe requires frame and strength")
        frame = point["frame"]
        if not isinstance(frame, int) or isinstance(frame, bool) or not 1 <= frame <= 100000:
            raise ValueError("Invalid frame")
        validated.append((frame, _finite(point["strength"], 0, 100, "strength")))
    if any(b[0] <= a[0] for a, b in zip(validated, validated[1:], strict=False)):
        raise ValueError("Frames must be strictly increasing")
    socket = mat.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"]
    for frame, value in validated:
        socket.default_value = value
        socket.keyframe_insert(data_path="default_value", frame=frame)
    return len(validated)


def animate_curve_reveal(curve_name: str, *, start_frame: int, end_frame: int) -> dict:
    """Keyframe a bevelled curve's visible length; no scene-wide side effects."""
    obj = bpy.data.objects.get(curve_name)
    if obj is None or obj.type != "CURVE" or obj.data.bevel_depth <= 0:
        raise ValueError("Existing bevelled CURVE object required")
    if (
        not isinstance(start_frame, int)
        or not isinstance(end_frame, int)
        or not 1 <= start_frame < end_frame <= 100000
    ):
        raise ValueError("Invalid reveal frame interval")
    curve = obj.data
    curve.bevel_factor_end = 0.0
    curve.keyframe_insert(data_path="bevel_factor_end", frame=start_frame)
    curve.bevel_factor_end = 1.0
    curve.keyframe_insert(data_path="bevel_factor_end", frame=end_frame)
    return {"object": obj.name, "start": start_frame, "end": end_frame}


def set_object_interpolation(object_name: str, *, property_path: str, interpolation: str) -> int:
    """Set interpolation only on existing transform keyframes; refuse other RNA."""
    paths = {"location", "scale", "rotation_euler"}
    if property_path not in paths or interpolation not in {"LINEAR", "BEZIER", "CONSTANT"}:
        raise ValueError("Unsupported property or interpolation")
    obj = bpy.data.objects.get(object_name)
    if obj is None or not obj.animation_data or not obj.animation_data.action:
        raise ValueError("Object with animation required")
    action = obj.animation_data.action
    try:
        curves = list(action.fcurves)
    except AttributeError as exc:
        raise ValueError("Unsupported Blender Action structure; use a qualified version") from exc
    matching = [fc for fc in curves if fc.data_path == property_path]
    if not matching:
        raise ValueError("No matching animation curve")
    count = 0
    for fc in matching:
        for key in fc.keyframe_points:
            key.interpolation = interpolation
            count += 1
    return count


def configure_ortho_camera(
    camera_name: str, *, scale: float, shift_x: float = 0, shift_y: float = 0
) -> dict:
    obj = bpy.data.objects.get(camera_name)
    if obj is None or obj.type != "CAMERA":
        raise ValueError("Camera object required")
    scale = _finite(scale, 0.01, 100000, "scale")
    shift_x = _finite(shift_x, -2, 2, "shift_x")
    shift_y = _finite(shift_y, -2, 2, "shift_y")
    obj.data.type = "ORTHO"
    obj.data.ortho_scale = scale
    obj.data.shift_x = shift_x
    obj.data.shift_y = shift_y
    return {
        "camera": obj.name,
        "scale": obj.data.ortho_scale,
        "shift_x": obj.data.shift_x,
        "shift_y": obj.data.shift_y,
    }
