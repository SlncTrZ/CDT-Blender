"""Common object-query tool schemas.
Wing: blender | Topic: object-query | Updated: 2026-09-14 18:31
"""

from mcp import types

_FILTER_PROPERTIES = {
    "type": {
        "type": "string",
        "description": "Optional Blender object type filter such as MESH, CURVE, LIGHT or CAMERA.",
    },
    "collection": {
        "type": "string",
        "description": "Optional exact collection-name filter.",
    },
}


def get_object_query_tools() -> list[types.Tool]:
    """Return common object list/get/count tools for the active Blender scene."""
    return [
        types.Tool(
            name="object_list",
            description=(
                "List objects in the active Blender scene in deterministic name order. "
                "Results are bounded and may be filtered by object type or collection."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    **_FILTER_PROPERTIES,
                    "offset": {
                        "type": "integer",
                        "minimum": 0,
                        "default": 0,
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 1000,
                        "default": 200,
                    },
                },
            },
        ),
        types.Tool(
            name="object_get",
            description=(
                "Get one object from the active Blender scene by its current exact Blender name, "
                "including common fields and Blender-specific extension data."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "minLength": 1,
                        "description": "Current exact Blender object name.",
                    }
                },
                "required": ["name"],
            },
        ),
        types.Tool(
            name="object_count",
            description=(
                "Count objects in the active Blender scene, optionally filtered by object type "
                "or exact collection name; includes counts grouped by Blender object type."
            ),
            inputSchema={"type": "object", "properties": dict(_FILTER_PROPERTIES)},
        ),
    ]
