# blender_mcp_addon/tools/modeling/__init__.py

from .architectural import ModelingArchitectural
from .curves import ModelingCurves
from .modifiers import ModelingModifiers
from .operators import ModelingOperators
from .primitives import ModelingPrimitives
from .selection import ModelingSelection
from .systems import ModelingSystems
from .transforms import ModelingTransforms
from .uv import ModelingUV


class ModelingTools(
    ModelingPrimitives,
    ModelingCurves,
    ModelingModifiers,
    ModelingTransforms,
    ModelingSelection,
    ModelingOperators,
    ModelingArchitectural,
    ModelingSystems,
    ModelingUV,
):
    """Refactored Modeling Tools for Blender MCP"""

    pass
