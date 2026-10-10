"""Curated bounded Geometry Nodes presets for 2D/2.5D infographic particle motifs."""

from __future__ import annotations

import math
import re

import bpy  # type: ignore

from .infographic_native import _hex_rgba


def validate_particle_preset(
    name: str,
    *,
    mode: str,
    count: int,
    radius: float,
    start: tuple[float, float, float],
    end: tuple[float, float, float],
    color: str,
    frame_start: int,
    frame_end: int,
) -> dict:
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", name):
        raise ValueError("Invalid Geometry Nodes name")
    if mode not in {"LINE", "RING"}:
        raise ValueError("Geometry Nodes mode must be LINE or RING")
    if isinstance(count, bool) or not isinstance(count, int) or not 2 <= count <= 256:
        raise ValueError("Particle count must be 2..256")
    if (
        isinstance(radius, bool)
        or not isinstance(radius, (int, float))
        or not math.isfinite(radius)
        or not 0.005 <= radius <= 5
    ):
        raise ValueError("Particle radius invalid")
    for vec in (start, end):
        if (
            not isinstance(vec, (list, tuple))
            or len(vec) != 3
            or any(
                isinstance(v, bool)
                or not isinstance(v, (int, float))
                or not math.isfinite(v)
                or abs(v) > 10000
                for v in vec
            )
        ):
            raise ValueError("Particle vector invalid")
    if (
        isinstance(frame_start, bool)
        or isinstance(frame_end, bool)
        or not isinstance(frame_start, int)
        or not isinstance(frame_end, int)
        or not 1 <= frame_start < frame_end <= 100000
    ):
        raise ValueError("Particle animation frames invalid")
    rgba = _hex_rgba(color)
    if mode == "LINE" and math.dist(start, end) <= 0.001:
        raise ValueError("Particle line endpoints must differ")
    return {"rgba": rgba}


def create_particle_preset(
    name: str,
    *,
    mode: str = "LINE",
    count: int = 25,
    radius: float = 0.04,
    color: str = "#53E9FF",
    start: tuple[float, float, float] = (-2, 0, 0),
    end: tuple[float, float, float] = (2, 0, 0),
    ring_radius: float = 1.0,
    frame_start: int = 1,
    frame_end: int = 60,
) -> dict:
    """Create GN mesh-line/curve-ring -> instanced Icospheres, animated by object rotation.

    Uses only whitelisted GeometryNode types. No arbitrary node name or RNA path.
    """
    values = validate_particle_preset(
        name,
        mode=mode,
        count=count,
        radius=radius,
        start=start,
        end=end,
        color=color,
        frame_start=frame_start,
        frame_end=frame_end,
    )
    if (
        isinstance(ring_radius, bool)
        or not isinstance(ring_radius, (int, float))
        or not math.isfinite(ring_radius)
        or not 0.1 <= ring_radius <= 100
    ):
        raise ValueError("Invalid ring radius")
    if any(
        (
            bpy.data.objects.get(name),
            bpy.data.node_groups.get(name + "_GN"),
            bpy.data.meshes.get(name + "_MESH"),
            bpy.data.materials.get(name + "_MAT"),
        )
    ):
        raise ValueError("Geometry preset names already in use")
    rgba = values["rgba"]
    mat = bpy.data.materials.new(name + "_MAT")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Emission Color"].default_value = rgba
    bsdf.inputs["Emission Strength"].default_value = 2.0

    group = bpy.data.node_groups.new(name + "_GN", "GeometryNodeTree")
    group.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    nodes = group.nodes
    links = group.links
    output = nodes.new("NodeGroupOutput")
    if mode == "LINE":
        source = nodes.new("GeometryNodeMeshLine")
        source.mode = "OFFSET"
        source.inputs["Count"].default_value = count
        source.inputs["Start Location"].default_value = start
        source.inputs["Offset"].default_value = tuple(
            (b - a) / (count - 1) for a, b in zip(start, end, strict=True)
        )
        points = source.outputs["Mesh"]
    else:
        circle = nodes.new("GeometryNodeCurvePrimitiveCircle")
        circle.inputs["Resolution"].default_value = count
        circle.inputs["Radius"].default_value = ring_radius
        resample = nodes.new("GeometryNodeResampleCurve")
        resample.mode = "COUNT"
        resample.inputs["Count"].default_value = count
        links.new(circle.outputs["Curve"], resample.inputs["Curve"])
        points = resample.outputs["Curve"]
    icosphere = nodes.new("GeometryNodeMeshIcoSphere")
    icosphere.inputs["Radius"].default_value = radius
    icosphere.inputs["Subdivisions"].default_value = 1
    apply_mat = nodes.new("GeometryNodeSetMaterial")
    apply_mat.inputs["Material"].default_value = mat
    links.new(icosphere.outputs["Mesh"], apply_mat.inputs["Geometry"])
    instances = nodes.new("GeometryNodeInstanceOnPoints")
    links.new(points, instances.inputs["Points"])
    links.new(apply_mat.outputs["Geometry"], instances.inputs["Instance"])
    links.new(instances.outputs["Instances"], output.inputs["Geometry"])

    mesh = bpy.data.meshes.new(name + "_MESH")
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    mod = obj.modifiers.new("Infographic_Particles", "NODES")
    mod.node_group = group
    if mode == "RING":
        obj.rotation_euler.z = 0.0
        obj.keyframe_insert(data_path="rotation_euler", frame=frame_start)
        obj.rotation_euler.z = 2 * math.pi
        obj.keyframe_insert(data_path="rotation_euler", frame=frame_end)
    return {
        "object": obj.name,
        "node_group": group.name,
        "particle_count": count,
        "mode": mode,
        "animated_rotation": mode == "RING",
    }
