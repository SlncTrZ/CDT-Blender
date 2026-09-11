# blender_mcp_bridge/tools/modeling/__init__.py

from mcp import types

from .curves import get_curve_tools
from .modifiers import get_modifier_tools
from .operators import get_operator_tools
from .primitives import get_primitive_tools
from .selection import get_selection_tools
from .transforms import get_transform_tools

# CDT fork: discipline builders (architectural rooms/walls, MEP pipe/cable-tray
# systems) are QUARANTINED from the provider contract. The addon handlers stay
# in place but are never advertised or dispatched by the bridge. Discipline
# objects belong to CDT_Engineer Production Domains.


def get_modeling_tools() -> list[types.Tool]:
    """Returns all modeling-related tools"""
    tools = []
    tools.extend(get_primitive_tools())
    tools.extend(get_curve_tools())
    tools.extend(get_modifier_tools())
    tools.extend(get_transform_tools())
    tools.extend(get_selection_tools())
    tools.extend(get_operator_tools())
    return tools
