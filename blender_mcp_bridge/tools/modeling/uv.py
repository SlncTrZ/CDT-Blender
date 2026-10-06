# blender_mcp_bridge/tools/modeling/uv.py
"""MCP tool schemas for Blender modeling UV unwrap / projection."""

from mcp import types


def get_uv_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="unwrap_mesh",
            description=(
                "Unwrap the UVs of a mesh object using Blender's native unwrap operator. "
                "Selects all faces and unwraps the whole mesh, then reports UV read-back "
                "(UV layers, loop count, non-zero coordinates)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "object_name": {
                        "type": "string",
                        "description": "Name of the mesh object to unwrap",
                    },
                    "method": {
                        "type": "string",
                        "enum": ["ANGLE_BASED", "CONFORMAL"],
                        "default": "ANGLE_BASED",
                        "description": "Unwrap method",
                    },
                    "fill_holes": {
                        "type": "boolean",
                        "default": True,
                        "description": "Fill holes in the UV mapping",
                    },
                    "correct_aspect": {
                        "type": "boolean",
                        "default": True,
                        "description": "Correct UV aspect ratio",
                    },
                    "use_subsurf_data": {
                        "type": "boolean",
                        "default": False,
                        "description": "Unwrap using subdivision-surface data",
                    },
                    "margin": {
                        "type": "number",
                        "default": 0.001,
                        "description": "Margin between UV islands",
                    },
                },
                "required": ["object_name"],
            },
        ),
        types.Tool(
            name="smart_project",
            description=(
                "Project UVs onto a mesh object using Blender's Smart UV Project. "
                "Automatically lays out UV islands based on face angles, then reports "
                "UV read-back (UV layers, loop count, non-zero coordinates)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "object_name": {
                        "type": "string",
                        "description": "Name of the mesh object to project",
                    },
                    "angle_limit": {
                        "type": "number",
                        "default": 66.0,
                        "description": "Angle limit in degrees for splitting UV islands",
                    },
                    "island_margin": {
                        "type": "number",
                        "default": 0.0,
                        "description": "Margin between UV islands",
                    },
                    "area_weight": {
                        "type": "number",
                        "default": 0.0,
                        "description": (
                            "Area weighting (0.0 = uniform, 1.0 = proportional to face area)"
                        ),
                    },
                    "correct_aspect": {
                        "type": "boolean",
                        "default": True,
                        "description": "Correct UV aspect ratio",
                    },
                    "scale_to_bounds": {
                        "type": "boolean",
                        "default": False,
                        "description": "Scale UVs to fit within bounds",
                    },
                },
                "required": ["object_name"],
            },
        ),
    ]
