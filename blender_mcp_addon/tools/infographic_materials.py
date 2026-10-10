"""Internal bounded material controls for infographic production.

No dynamic shader-node type names or arbitrary socket paths accepted.
"""

from __future__ import annotations

import math

import bpy  # type: ignore

from .infographic_native import _hex_rgba

_SCALAR_SOCKETS = {
    "metallic": ("Metallic", 0.0, 1.0),
    "roughness": ("Roughness", 0.0, 1.0),
    "transmission": ("Transmission Weight", 0.0, 1.0),
    "ior": ("IOR", 1.0, 3.0),
    "alpha": ("Alpha", 0.0, 1.0),
    "emission_strength": ("Emission Strength", 0.0, 100.0),
}
_COLOR_SOCKETS = {"base_color": "Base Color", "emission_color": "Emission Color"}


def _bsdf(material_name: str):
    if not isinstance(material_name, str) or not material_name:
        raise ValueError("Material name required")
    material = bpy.data.materials.get(material_name)
    if not material or not material.use_nodes or not material.node_tree:
        raise ValueError("Existing node material required")
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    if bsdf is None:
        raise ValueError("Principled BSDF required")
    return material, bsdf


def _validate_scalar(key: str, value: object) -> float:
    if key not in _SCALAR_SOCKETS:
        raise ValueError("Unsupported material property")
    _, low, high = _SCALAR_SOCKETS[key]
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not low <= value <= high
    ):
        raise ValueError(f"{key} must be finite within [{low}, {high}]")
    return float(value)


def update_material(
    material_name: str,
    *,
    scalars: dict | None = None,
    colors: dict | None = None,
    render_method: str | None = None,
    require_single_user: bool = True,
) -> dict:
    """Validate all requested changes before touching any material socket.

    Refuses shared materials by default to prevent unexpected cross-object edits.
    """
    mat, bsdf = _bsdf(material_name)
    if require_single_user and mat.users > 1:
        raise ValueError("Shared material requires explicit opt-in")
    scalars = {} if scalars is None else scalars
    colors = {} if colors is None else colors
    if not isinstance(scalars, dict) or not isinstance(colors, dict):
        raise ValueError("scalars and colors must be objects")
    if not scalars and not colors and render_method is None:
        raise ValueError("At least one material property required")
    checked_scalars = {k: _validate_scalar(k, v) for k, v in scalars.items()}
    checked_colors = {}
    for key, value in colors.items():
        if key not in _COLOR_SOCKETS:
            raise ValueError("Unsupported material color")
        checked_colors[key] = _hex_rgba(value)
    if render_method is not None and render_method not in {"DITHERED", "BLENDED"}:
        raise ValueError("Unsupported render method")
    if render_method is not None and not hasattr(mat, "surface_render_method"):
        raise ValueError("Render method unsupported by Blender version")
    for key in checked_scalars:
        if bsdf.inputs.get(_SCALAR_SOCKETS[key][0]) is None:
            raise ValueError(f"Blender shader socket unavailable: {key}")
    for key in checked_colors:
        if bsdf.inputs.get(_COLOR_SOCKETS[key]) is None:
            raise ValueError(f"Blender shader socket unavailable: {key}")
    for key, value in checked_scalars.items():
        bsdf.inputs[_SCALAR_SOCKETS[key][0]].default_value = value
    for key, value in checked_colors.items():
        bsdf.inputs[_COLOR_SOCKETS[key]].default_value = value
    if render_method is not None:
        mat.surface_render_method = render_method
    return {
        "material": mat.name,
        "scalars": checked_scalars,
        "colors": {k: list(v) for k, v in checked_colors.items()},
        "render_method": getattr(mat, "surface_render_method", None),
        "users": mat.users,
    }


def animate_material_property(
    material_name: str,
    *,
    property_name: str,
    keyframes: list[dict],
    require_single_user: bool = True,
) -> dict:
    """Animate bounded Principled scalar/color socket; no arbitrary RNA paths."""
    mat, bsdf = _bsdf(material_name)
    if require_single_user and mat.users > 1:
        raise ValueError("Shared material requires explicit opt-in")
    if property_name not in _SCALAR_SOCKETS and property_name not in _COLOR_SOCKETS:
        raise ValueError("Unsupported animated material property")
    if not isinstance(keyframes, list) or not 2 <= len(keyframes) <= 64:
        raise ValueError("Require 2..64 keyframes")
    checked = []
    for item in keyframes:
        if not isinstance(item, dict) or set(item) != {"frame", "value"}:
            raise ValueError("Keyframes require frame and value")
        frame = item["frame"]
        if isinstance(frame, bool) or not isinstance(frame, int) or not 1 <= frame <= 100000:
            raise ValueError("Invalid keyframe index")
        value = (
            _validate_scalar(property_name, item["value"])
            if property_name in _SCALAR_SOCKETS
            else _hex_rgba(item["value"])
        )
        checked.append((frame, value))
    if any(b[0] <= a[0] for a, b in zip(checked, checked[1:], strict=False)):
        raise ValueError("Keyframes must be strictly increasing")
    socket_name = (
        _SCALAR_SOCKETS[property_name][0]
        if property_name in _SCALAR_SOCKETS
        else _COLOR_SOCKETS[property_name]
    )
    socket = bsdf.inputs.get(socket_name)
    if socket is None:
        raise ValueError("Blender shader socket unavailable")
    for frame, value in checked:
        socket.default_value = value
        socket.keyframe_insert(data_path="default_value", frame=frame)
    return {"material": mat.name, "property": property_name, "frames": [f for f, _ in checked]}
