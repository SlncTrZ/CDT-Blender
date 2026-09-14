"""Common organization tool schemas.
Wing: blender | Topic: organization | Updated: 2026-09-14 18:51
"""

from mcp import types


def get_organization_tools() -> list[types.Tool]:
    """Return common organization operations backed by Blender collections."""
    return [
        types.Tool(
            name="organization_list",
            description=(
                "List Blender collections reachable from the active scene as common organizations. "
                "Results are deterministic, bounded, and include hierarchy and Blender visibility metadata."
            ),
            inputSchema={
                "type": "object",
                "properties": {
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
        )
    ]
