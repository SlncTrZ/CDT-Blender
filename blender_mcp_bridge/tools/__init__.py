# blender_mcp_bridge/tools/__init__.py

from mcp import types

from .animation import get_animation_tools
from .camera import get_camera_tools
from .collections import get_collection_tools
from .design_rules import get_design_rule_tools
from .document import get_document_tools
from .history import get_history_tools
from .infographic import get_infographic_tools
from .interchange import get_interchange_tools
from .lifecycle import get_lifecycle_tools
from .lighting import get_lighting_tools
from .materials import get_material_tools
from .modeling import get_modeling_tools
from .object_query import get_object_query_tools
from .organization import get_organization_tools
from .printing import get_printing_tools
from .provider import get_provider_tools
from .rendering import get_rendering_tools
from .scene import get_scene_tools
from .sculpting import get_sculpting_tools
from .transform import get_common_transform_tools

# Mutation vs read-only classification. Mirrors blender_mcp_addon/lifecycle.py
# (READ_ONLY_COMMANDS + is_mutation) so op_id is exposed on exactly the tools
# whose addon handlers can mutate Blender state. Keep the two in sync.
_NON_MUTATION_TOOLS = frozenset(
    {
        # Provider contract — answered locally by the bridge, never reaches Blender.
        "help",
        "system_status",
        "system_capabilities",
        # Design-rule lookups — answered locally by the bridge, never reaches Blender.
        "check_design",
        "get_design_rules",
        "list_design_topics",
        # Lifecycle recovery — already carries op_id as a required argument.
        "reconcile_operation",
        "operation_status",
        # Read-only queries — no side effects.
        "document_info",
        "object_list",
        "object_get",
        "object_count",
        "organization_list",
        "check_mesh_for_printing",
    }
)

_OP_ID_SCHEMA = {
    "type": "string",
    "description": (
        "Optional stable operation ID (idempotency key) for this mutation. "
        "Reusing the same op_id with the same payload returns the cached outcome "
        "instead of re-running the side effect; reusing it with a different payload "
        "is rejected as a conflict. Omit to auto-generate one."
    ),
    "maxLength": 128,
}


def is_mutation_tool(name: str) -> bool:
    """True when a tool's addon handler mutates Blender state (needs an op_id)."""
    if not name:
        return False
    if name.startswith("get_"):
        return False
    return name not in _NON_MUTATION_TOOLS


def _inject_op_id(tools: list[types.Tool]) -> list[types.Tool]:
    """Add the op_id idempotency key to every mutation tool's inputSchema."""
    for tool in tools:
        if not is_mutation_tool(tool.name):
            continue
        properties = tool.inputSchema.setdefault("properties", {})
        properties.setdefault("op_id", _OP_ID_SCHEMA)
    return tools


def get_mcp_tools() -> list[types.Tool]:
    """Returns all Blender tools from all modules"""
    tools = []
    # SlncTrZ provider contract FIRST (help, system_status, system_capabilities)
    tools.extend(get_provider_tools())
    tools.extend(get_lifecycle_tools())
    tools.extend(get_document_tools())
    tools.extend(get_object_query_tools())
    tools.extend(get_organization_tools())
    tools.extend(get_common_transform_tools())
    tools.extend(get_scene_tools())
    tools.extend(get_collection_tools())
    tools.extend(get_modeling_tools())
    tools.extend(get_material_tools())
    tools.extend(get_lighting_tools())
    tools.extend(get_camera_tools())
    tools.extend(get_animation_tools())
    tools.extend(get_rendering_tools())
    tools.extend(get_history_tools())
    tools.extend(get_infographic_tools())
    tools.extend(get_interchange_tools())
    tools.extend(get_printing_tools())
    tools.extend(get_sculpting_tools())
    tools.extend(get_design_rule_tools())
    return _inject_op_id(tools)
