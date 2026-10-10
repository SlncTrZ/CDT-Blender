"""Bounded offline SVG -> Blender Curve import; internal until public contract review.

For SVG without linked assets, scripting, embedded data, or imported fonts.
This is a deliberately limited SVG profile, not a general browser SVG renderer.
"""

from __future__ import annotations

import math
import os
import re
from xml.etree import ElementTree as ET

_SVG_NS = "http://www.w3.org/2000/svg"
_SUPPORTED = frozenset(
    {"svg", "g", "path", "rect", "circle", "ellipse", "line", "polyline", "polygon"}
)
_ALLOWED_ATTRS = frozenset(
    {
        "viewBox",
        "width",
        "height",
        "version",
        "id",
        "fill",
        "stroke",
        "stroke-width",
        "opacity",
        "fill-opacity",
        "stroke-opacity",
        "transform",
        "d",
        "points",
        "x",
        "y",
        "x1",
        "y1",
        "x2",
        "y2",
        "cx",
        "cy",
        "r",
        "rx",
        "ry",
        "fill-rule",
        "stroke-linecap",
        "stroke-linejoin",
        "stroke-miterlimit",
        "style",
    }
)
_NUMBERS = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
_FORBIDDEN = (
    b"<!doctype",
    b"<!entity",
    b"<![cdata[",
    b"<?",
    b"data:",
    b"javascript:",
    b"url(",
    b"@import",
)
_SAFE_ATTR_VALUE = re.compile(r"^[\w\s.,+\-#%():;/]*$", re.UNICODE)
_STYLE_PROPERTIES = frozenset(
    {
        "fill",
        "stroke",
        "stroke-width",
        "opacity",
        "fill-opacity",
        "stroke-opacity",
        "fill-rule",
        "stroke-linecap",
        "stroke-linejoin",
    }
)
_STYLE_COLOR = re.compile(r"(?:#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?|none)\Z")
_STYLE_NUM = re.compile(r"(?:\d+(?:\.\d*)?|\.\d+)\Z")


def _validate_inline_style(value: str) -> None:
    """Allow only isolated presentation attributes, not CSS execution."""
    if not value or len(value) > 512:
        raise ValueError("SVG inline style must be 1..512 characters")
    for declaration in value.strip().rstrip(";").split(";"):
        if declaration.count(":") != 1:
            raise ValueError("Invalid SVG inline style declaration")
        key, raw_value = (part.strip() for part in declaration.split(":", 1))
        if key not in _STYLE_PROPERTIES or not raw_value:
            raise ValueError("Unsupported SVG style property")
        if key in {"fill", "stroke"} and not _STYLE_COLOR.fullmatch(raw_value):
            raise ValueError("Unsupported SVG style color")
        if key in {"stroke-width", "opacity", "fill-opacity", "stroke-opacity"}:
            high = 1000 if key == "stroke-width" else 1
            if not _STYLE_NUM.fullmatch(raw_value) or float(raw_value) > high:
                raise ValueError("Unsafe SVG style numeric value")
        if key == "fill-rule" and raw_value not in {"evenodd", "nonzero"}:
            raise ValueError("Unsupported SVG fill rule")
        if key == "stroke-linecap" and raw_value not in {"butt", "round", "square"}:
            raise ValueError("Unsupported SVG linecap")
        if key == "stroke-linejoin" and raw_value not in {"miter", "round", "bevel"}:
            raise ValueError("Unsupported SVG linejoin")


def validate_svg_document(data: bytes) -> dict:
    """Return bounded shape inventory, or refuse BEFORE any Blender mutation."""
    if not isinstance(data, bytes) or not 0 < len(data) <= 256 * 1024:
        raise ValueError("SVG must be 1..262144 bytes")
    content = data.lstrip(b"\xef\xbb\xbf \t\r\n")
    # Permit inert UTF-8 XML declaration; reject all other PIs/entities.
    if content.startswith(b"<?xml"):
        closing = content.find(b"?>")
        if (
            closing < 0
            or closing > 100
            or not re.fullmatch(
                rb"<\?xml\s+version=[\"']1\.[01][\"'](?:\s+encoding=[\"']UTF-8[\"'])?\s*\?>",
                content[: closing + 2],
                flags=re.I,
            )
        ):
            raise ValueError("Only a standard UTF-8 XML declaration is supported")
        content = content[closing + 2 :]
    lowered = content.lower()
    if any(token in lowered for token in _FORBIDDEN):
        raise ValueError("SVG active content/entities/external references refused")
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        raise ValueError("Malformed SVG document") from exc
    if root.tag != f"{{{_SVG_NS}}}svg":
        raise ValueError("SVG root must use the official SVG namespace")
    nodes = 0
    shapes = 0
    stack = [(root, 0)]
    while stack:
        node, depth = stack.pop()
        if depth > 12 or nodes >= 256:
            raise ValueError("SVG too deep or too many elements")
        local = node.tag.removeprefix(f"{{{_SVG_NS}}}")
        if local not in _SUPPORTED or node.tag != f"{{{_SVG_NS}}}{local}":
            raise ValueError(f"SVG element not supported: {local}")
        if node.text and node.text.strip():
            raise ValueError("SVG text nodes/embedded scripts not supported")
        if node.tail and node.tail.strip():
            raise ValueError("SVG trailing text not supported")
        for key, value in node.attrib.items():
            if key not in _ALLOWED_ATTRS or len(value) > 20480:
                raise ValueError(f"SVG attribute not supported: {key}")
            if not _SAFE_ATTR_VALUE.fullmatch(value) or any(
                marker in value.lower()
                for marker in ("http", "url(", "file:", "javascript:", "data:", "\\")
            ):
                raise ValueError("SVG external/active/unsafe attribute refused")
            if key == "style":
                _validate_inline_style(value)
            if key in {"d", "points"}:
                if len(_NUMBERS.findall(value)) > 4096:
                    raise ValueError("SVG shape has too many coordinates")
            if key in {
                "viewBox",
                "width",
                "height",
                "transform",
                "d",
                "points",
                "x",
                "y",
                "x1",
                "y1",
                "x2",
                "y2",
                "cx",
                "cy",
                "r",
                "rx",
                "ry",
                "stroke-width",
                "stroke-miterlimit",
                "opacity",
                "fill-opacity",
                "stroke-opacity",
            }:
                for number in _NUMBERS.findall(value):
                    try:
                        n = float(number)
                    except ValueError as exc:
                        raise ValueError("Invalid SVG numeric attribute") from exc
                    if not -100000 <= n <= 100000:
                        raise ValueError("SVG coordinate out of permitted bounds")
        nodes += 1
        if local not in {"svg", "g"}:
            shapes += 1
        stack.extend((child, depth + 1) for child in node)
    if not 1 <= shapes <= 128:
        raise ValueError("SVG must contain 1..128 supported shapes")
    return {
        "elements": nodes,
        "shapes": shapes,
        "profile": "offline-basic-2d",
        "inline_style_supported": True,
    }


def import_svg_curves(
    filepath: str,
    *,
    prefix: str,
    allow_roots: list[str] | tuple[str, ...],
    target_width: float | None = None,
    location: tuple[float, float, float] | None = None,
) -> dict:
    """Import a vetted standalone SVG via Blender's SVG curves importer.

    Requires supplied allowed roots and a context supporting import_curve.svg.
    The imported objects only are renamed and returned; no user objects touched.
    """
    if not isinstance(filepath, str) or not filepath.lower().endswith(".svg"):
        raise ValueError("SVG filepath extension required")
    if not isinstance(prefix, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,47}", prefix):
        raise ValueError("Invalid SVG object prefix")
    if target_width is not None and (
        isinstance(target_width, bool)
        or not isinstance(target_width, (int, float))
        or not math.isfinite(target_width)
        or not 0.01 <= target_width <= 1000
    ):
        raise ValueError("Invalid SVG target width")
    if location is not None and (
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
        raise ValueError("Invalid SVG placement")
    from ..utils import require_allowed

    # Resolves Windows junctions/symlinks as required by existing provider policy.
    path = require_allowed(filepath, allow_roots)
    if not os.path.isfile(path):
        raise ValueError("SVG file does not exist")
    with open(path, "rb") as handle:
        data = handle.read(256 * 1024 + 1)
    metadata = validate_svg_document(data)
    import bpy  # type: ignore

    if any(obj.name.startswith(f"{prefix}_") for obj in bpy.data.objects):
        raise ValueError("SVG prefix already used by a scene object")
    before = {obj.as_pointer() for obj in bpy.data.objects}
    try:
        result = bpy.ops.import_curve.svg(filepath=path)
        if "FINISHED" not in result:
            raise ValueError(f"SVG Blender importer returned {result}")
        new_objects = sorted(
            (obj for obj in bpy.data.objects if obj.as_pointer() not in before),
            key=lambda obj: obj.name,
        )
        if not 1 <= len(new_objects) <= 128:
            raise ValueError("SVG imported an unexpected object count")
        if any(obj.type != "CURVE" for obj in new_objects):
            raise ValueError("SVG importer returned non-CURVE object")
        if target_width is not None or location is not None:
            from mathutils import Vector  # type: ignore

            bpy.context.view_layer.update()
            corners = [
                obj.matrix_world @ Vector(corner) for obj in new_objects for corner in obj.bound_box
            ]
            mins = [min(vec[axis] for vec in corners) for axis in range(3)]
            width = max(vec.x for vec in corners) - mins[0]
            if width <= 1e-9:
                raise ValueError("SVG imported geometry has zero width")
            factor = target_width / width if target_width is not None else 1.0
            origin = location if location is not None else (0.0, 0.0, 0.0)
            for obj in new_objects:
                old_position = tuple(obj.location)
                obj.scale = tuple(value * factor for value in obj.scale)
                obj.location = tuple(
                    (old_position[i] - mins[i]) * factor + origin[i] for i in range(3)
                )
        for index, obj in enumerate(new_objects):
            obj.name = f"{prefix}_{index:03d}"
    except Exception:
        # Compensation only for objects created in this invocation.
        for obj in list(bpy.data.objects):
            if obj.as_pointer() not in before:
                bpy.data.objects.remove(obj, do_unlink=True)
        raise
    return {"objects": [obj.name for obj in new_objects], **metadata}
