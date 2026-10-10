"""Narrow error typing for the public L2 motion-infographic addon handlers.

Existing modeling/sculpt/document tools keep their original error contracts.
"""

from __future__ import annotations

L2_TOOL_NAMES = frozenset(
    {
        "import_svg_curves",
        "create_grease_strokes",
        "create_filled_grease_tween",
        "create_particle_preset",
        "create_animated_particle_grid",
        "create_unicode_text",
        "create_shaped_text_plane",
    }
)


def validation_refusal(command: str, error: BaseException) -> dict | None:
    """Translate L2 input validation failures into typed non-retryable errors."""
    if command in L2_TOOL_NAMES and isinstance(error, ValueError):
        return {
            "status": "error",
            "kind": "validation_error",
            "retryable": False,
            "message": str(error),
        }
    return None
