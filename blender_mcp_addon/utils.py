# blender_mcp_addon/utils.py

import os

import bpy  # type: ignore


def hex_to_rgb(hex_color):
    """Convert hex color string to RGB tuple"""
    if isinstance(hex_color, str) and hex_color.startswith("#"):
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i : i + 2], 16) / 255.0 for i in (0, 2, 4))
    return hex_color


def get_object(name):
    """Get object by name with error handling"""
    obj = bpy.data.objects.get(name)
    if not obj:
        raise ValueError(f"Object '{name}' not found")
    return obj


def get_collection(name):
    """Get collection by name, creating it if it doesn't exist"""
    coll = bpy.data.collections.get(name)
    if not coll:
        coll = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(coll)
    return coll


def _canonical(path):
    """Canonical form for containment checks: realpath resolves symlinks/junctions."""
    return os.path.normcase(os.path.realpath(os.path.abspath(path)))


def _path_is_allowed(path, allow_roots):
    """True when path sits inside one of the allow-roots. Missing roots fail closed."""
    if not allow_roots:
        return False
    needle = _canonical(path)
    for root in allow_roots:
        canonical_root = _canonical(root)
        try:
            if os.path.commonpath([needle, canonical_root]) == canonical_root:
                return True
        except ValueError:
            continue
    return False


class OutsideAllowRoots(ValueError):
    """A caller-controlled file argument resolves outside BLENDER_ALLOW_ROOTS."""


def _absolute_for_check(path):
    """Absolute form of a Blender path for containment checks.

    Blender-relative '//' paths resolve against the current .blend directory
    (or the process CWD when unsaved); everything else via abspath.
    """
    if isinstance(path, str) and path.startswith("//"):
        try:
            blend_file = bpy.data.filepath
        except Exception:
            blend_file = ""
        base = os.path.dirname(os.path.abspath(blend_file)) if blend_file else os.getcwd()
        return os.path.normpath(os.path.join(base, path[2:]))
    return os.path.abspath(path)


def require_allowed(path, allow_roots):
    """Fail closed when path escapes allow-roots; returns the absolute path otherwise."""
    absolute = _absolute_for_check(path)
    if not _path_is_allowed(absolute, allow_roots):
        raise OutsideAllowRoots(f"Path is outside the configured allow-roots: {path}")
    return absolute


DEFAULT_HOST = (
    os.environ.get("BLENDER_ADDON_HOST") or os.environ.get("BLENDER_MCP_HOST") or "127.0.0.1"
)
DEFAULT_PORT = int(
    os.environ.get("BLENDER_ADDON_PORT") or os.environ.get("BLENDER_MCP_PORT") or 8888
)
