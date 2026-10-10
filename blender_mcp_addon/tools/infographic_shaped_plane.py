"""Blender-side import of pre-shaped script text as transparent image geometry.

The caller must run a qualified RAQM/HarfBuzz/FriBidi shaping step beforehand.
This does not claim editable vector glyphs or perform hidden native shaping.
"""

from __future__ import annotations

import math
import os
import re

import bpy  # type: ignore


def create_shaped_text_plane(
    name: str,
    *,
    png_path: str,
    allow_roots: list[str] | tuple[str, ...],
    width: float = 3.0,
    location: tuple[float, float, float] = (0, 0, 0),
) -> dict:
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", name):
        raise ValueError("Invalid shaped text object name")
    if not isinstance(png_path, str) or not png_path.lower().endswith(".png"):
        raise ValueError("Shaped text requires a PNG")
    if (
        isinstance(width, bool)
        or not isinstance(width, (int, float))
        or not math.isfinite(width)
        or not 0.05 <= width <= 100
    ):
        raise ValueError("Invalid text plane width")
    if (
        not isinstance(location, (list, tuple))
        or len(location) != 3
        or any(
            isinstance(v, bool)
            or not isinstance(v, (int, float))
            or not math.isfinite(v)
            or abs(v) > 10000
            for v in location
        )
    ):
        raise ValueError("Invalid text plane location")
    from ..utils import require_allowed

    path = require_allowed(png_path, allow_roots)
    if not os.path.isfile(path) or not 67 <= os.path.getsize(path) <= 8 * 1024 * 1024:
        raise ValueError("Shaped PNG not found or exceeds asset bounds")
    with open(path, "rb") as handle:
        if handle.read(8) != b"\x89PNG\r\n\x1a\n":
            raise ValueError("Invalid PNG file signature")
    if any(
        (
            bpy.data.objects.get(name),
            bpy.data.meshes.get(name + "_MESH"),
            bpy.data.materials.get(name + "_MAT"),
        )
    ):
        raise ValueError("Text plane name already in use")

    image = bpy.data.images.load(path, check_existing=True)
    # Keep the .blend self-contained when the external shaping asset moves.
    image.pack()
    if image.size[0] < 1 or image.size[1] < 1 or image.size[0] > 4096 or image.size[1] > 1024:
        raise ValueError("Invalid shaped image dimensions")
    height = float(width) * image.size[1] / image.size[0]
    mesh = bpy.data.meshes.new(name + "_MESH")
    mesh.from_pydata(
        [
            (-width / 2, -height / 2, 0),
            (width / 2, -height / 2, 0),
            (width / 2, height / 2, 0),
            (-width / 2, height / 2, 0),
        ],
        [],
        [(0, 1, 2, 3)],
    )
    mesh.update()
    uv = mesh.uv_layers.new(name="UV")
    for polygon in mesh.polygons:
        for loop_idx, uv_pt in zip(
            polygon.loop_indices,
            [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
            strict=True,
        ):
            uv.data[loop_idx].uv = uv_pt
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = location

    mat = bpy.data.materials.new(name + "_MAT")
    mat.use_nodes = True
    if hasattr(mat, "surface_render_method"):
        mat.surface_render_method = "DITHERED"
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    texture = nodes.new("ShaderNodeTexImage")
    texture.image = image
    links.new(texture.outputs["Color"], bsdf.inputs["Base Color"])
    links.new(texture.outputs["Color"], bsdf.inputs["Emission Color"])
    links.new(texture.outputs["Alpha"], bsdf.inputs["Alpha"])
    bsdf.inputs["Emission Strength"].default_value = 1
    mesh.materials.append(mat)
    return {
        "object": name,
        "width": width,
        "height": height,
        "image": os.path.basename(path),
        "editable_text": False,
    }
