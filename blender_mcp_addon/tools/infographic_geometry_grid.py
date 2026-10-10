"""Curated animated Geometry Nodes particle-grid preset (Blender 4.5+).

Grid positions are animated through 4D Noise Texture W and GeometryNodeSetPosition.
Node types, socket names, material and instance counts are fixed, not caller code.
"""

from __future__ import annotations

import math
import re

import bpy  # type: ignore

from .infographic_native import _hex_rgba


def validate_grid_preset(
    *,
    name: str,
    rows: int,
    columns: int,
    spacing: float,
    amplitude: float,
    particle_radius: float,
    start_frame: int,
    end_frame: int,
    color: str,
) -> tuple[float, float, float, tuple]:
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", name):
        raise ValueError("Invalid GN grid name")
    if any(
        isinstance(v, bool) or not isinstance(v, int) or not 2 <= v <= 40 for v in (rows, columns)
    ):
        raise ValueError("Rows and columns must be 2..40")
    if rows * columns > 512:
        raise ValueError("Total grid particles must not exceed 512")
    numeric = [(spacing, 0.05, 10), (amplitude, 0, 5), (particle_radius, 0.005, 1)]
    for value, low, high in numeric:
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or not low <= value <= high
        ):
            raise ValueError("Invalid GN grid dimension or animation amplitude")
    if (
        isinstance(start_frame, bool)
        or isinstance(end_frame, bool)
        or not isinstance(start_frame, int)
        or not isinstance(end_frame, int)
        or not 1 <= start_frame < end_frame <= 100000
    ):
        raise ValueError("Invalid GN grid frame interval")
    return float(spacing), float(amplitude), float(particle_radius), _hex_rgba(color)


def create_animated_particle_grid(
    name: str,
    *,
    rows: int = 8,
    columns: int = 14,
    spacing: float = 0.25,
    amplitude: float = 0.22,
    particle_radius: float = 0.035,
    color: str = "#77E5FF",
    start_frame: int = 1,
    end_frame: int = 60,
) -> dict:
    """Create bounded GN grid with a true animated displacement field."""
    spacing, amplitude, particle_radius, rgba = validate_grid_preset(
        name=name,
        rows=rows,
        columns=columns,
        spacing=spacing,
        amplitude=amplitude,
        particle_radius=particle_radius,
        start_frame=start_frame,
        end_frame=end_frame,
        color=color,
    )
    if any(
        (
            bpy.data.objects.get(name),
            bpy.data.node_groups.get(name + "_GN"),
            bpy.data.meshes.get(name + "_MESH"),
            bpy.data.materials.get(name + "_MAT"),
        )
    ):
        raise ValueError("Geometry grid name already exists")
    mat = bpy.data.materials.new(name + "_MAT")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Emission Color"].default_value = rgba
    bsdf.inputs["Emission Strength"].default_value = 2.0
    group = bpy.data.node_groups.new(name + "_GN", "GeometryNodeTree")
    group.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    nodes, links = group.nodes, group.links
    out = nodes.new("NodeGroupOutput")
    grid = nodes.new("GeometryNodeMeshGrid")
    grid.inputs["Size X"].default_value = (columns - 1) * spacing
    grid.inputs["Size Y"].default_value = (rows - 1) * spacing
    grid.inputs["Vertices X"].default_value = columns
    grid.inputs["Vertices Y"].default_value = rows

    position = nodes.new("GeometryNodeInputPosition")
    noise = nodes.new("ShaderNodeTexNoise")
    noise.noise_dimensions = "4D"
    noise.inputs["Scale"].default_value = 1.8
    links.new(position.outputs["Position"], noise.inputs["Vector"])
    subtract = nodes.new("ShaderNodeMath")
    subtract.operation = "SUBTRACT"
    subtract.inputs[1].default_value = 0.5
    links.new(noise.outputs["Fac"], subtract.inputs[0])
    amplify = nodes.new("ShaderNodeMath")
    amplify.operation = "MULTIPLY"
    amplify.inputs[1].default_value = amplitude
    links.new(subtract.outputs["Value"], amplify.inputs[0])
    offset = nodes.new("ShaderNodeCombineXYZ")
    # Displace in the visible XY plane under an orthographic top-down camera.
    links.new(amplify.outputs["Value"], offset.inputs["Y"])
    set_position = nodes.new("GeometryNodeSetPosition")
    links.new(grid.outputs["Mesh"], set_position.inputs["Geometry"])
    links.new(offset.outputs["Vector"], set_position.inputs["Offset"])

    ico = nodes.new("GeometryNodeMeshIcoSphere")
    ico.inputs["Radius"].default_value = particle_radius
    ico.inputs["Subdivisions"].default_value = 1
    apply_mat = nodes.new("GeometryNodeSetMaterial")
    apply_mat.inputs["Material"].default_value = mat
    links.new(ico.outputs["Mesh"], apply_mat.inputs["Geometry"])
    inst = nodes.new("GeometryNodeInstanceOnPoints")
    links.new(set_position.outputs["Geometry"], inst.inputs["Points"])
    links.new(apply_mat.outputs["Geometry"], inst.inputs["Instance"])
    links.new(inst.outputs["Instances"], out.inputs["Geometry"])

    # Keyframe the noise's fourth dimension to animate the wave over time.
    noise.inputs["W"].default_value = 0.0
    noise.inputs["W"].keyframe_insert(data_path="default_value", frame=start_frame)
    noise.inputs["W"].default_value = 3.0
    noise.inputs["W"].keyframe_insert(data_path="default_value", frame=end_frame)

    mesh = bpy.data.meshes.new(name + "_MESH")
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    modifier = obj.modifiers.new("Infographic_WaveGrid", "NODES")
    modifier.node_group = group
    return {
        "object": obj.name,
        "node_group": group.name,
        "count": rows * columns,
        "rows": rows,
        "columns": columns,
        "wave_keyframes": [start_frame, end_frame],
    }
