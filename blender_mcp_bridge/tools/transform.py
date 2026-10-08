"""Common object-transform tool schemas.
Wing: blender | Topic: transform | Updated: 2026-09-14 19:04
"""

from mcp import types


def _xyz_vector(description: str) -> dict:
    return {
        "type": "array",
        "items": {"type": "number"},
        "minItems": 3,
        "maxItems": 3,
        "description": description,
    }


def get_common_transform_tools() -> list[types.Tool]:
    """Return common, explicitly-framed object transform operations."""
    return [
        types.Tool(
            name="object_move",
            description=(
                "Move one active-scene object by a WORLD-space XYZ delta. "
                "The object's world orientation and scale are preserved."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "minLength": 1},
                    "delta": _xyz_vector("WORLD-space translation delta [x, y, z]."),
                },
                "required": ["name", "delta"],
            },
        ),
        types.Tool(
            name="object_rotate",
            description=(
                "Rotate one active-scene object around its own origin by a WORLD-space Euler XYZ "
                "delta in degrees. Translation and scale are preserved. World matrices with shear "
                "are refused because decomposition would be lossy."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "minLength": 1},
                    "delta_degrees": _xyz_vector(
                        "WORLD-space Euler XYZ rotation delta in degrees [x, y, z]."
                    ),
                },
                "required": ["name", "delta_degrees"],
            },
        ),
        types.Tool(
            name="object_scale",
            description=(
                "Multiply one active-scene object's LOCAL-axis scale channels by XYZ factors. "
                "The object's location and rotation channels are preserved."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "minLength": 1},
                    "factors": _xyz_vector(
                        "Dimensionless multiplicative LOCAL-axis scale factors [x, y, z]."
                    ),
                },
                "required": ["name", "factors"],
            },
        ),
    ]
