"""Common object-transform contract tests.
Wing: blender | Topic: transform | Updated: 2026-09-14 19:00
"""

from __future__ import annotations

from blender_mcp_bridge import provider_contract
from blender_mcp_bridge.tools import get_mcp_tools
from blender_mcp_bridge.tools.transform import get_common_transform_tools

COMMON_TRANSFORM_TOOLS = {"object_move", "object_rotate", "object_scale"}


def test_common_transform_tools_are_public_and_unique():
    tools = get_common_transform_tools()
    names = [tool.name for tool in tools]

    assert set(names) == COMMON_TRANSFORM_TOOLS
    assert len(names) == len(set(names))
    assert COMMON_TRANSFORM_TOOLS <= {tool.name for tool in get_mcp_tools()}


def test_common_transform_vectors_are_exactly_xyz():
    tools = {tool.name: tool for tool in get_common_transform_tools()}
    fields = {
        "object_move": "delta",
        "object_rotate": "delta_degrees",
        "object_scale": "factors",
    }

    for tool_name, field in fields.items():
        schema = tools[tool_name].inputSchema
        vector = schema["properties"][field]
        assert schema["required"] == ["name", field]
        assert vector["type"] == "array"
        assert vector["minItems"] == 3
        assert vector["maxItems"] == 3


def test_common_transform_capability_claims_match_public_tools():
    for semantic in ("move", "rotate", "scale"):
        capability = provider_contract.CAPABILITIES[f"common.transform.{semantic}"]
        assert capability["supported"] is True
        assert capability["mode"] == "native"
