"""Common object-query contract tests.
Wing: blender | Topic: object-query | Updated: 2026-09-14 18:29
"""

from __future__ import annotations

from blender_mcp_bridge import provider_contract
from blender_mcp_bridge.tools import get_mcp_tools
from blender_mcp_bridge.tools.object_query import get_object_query_tools

OBJECT_QUERY_TOOLS = {"object_list", "object_get", "object_count"}


def test_common_object_query_tools_are_public_and_unique():
    tools = get_object_query_tools()
    names = [tool.name for tool in tools]

    assert set(names) == OBJECT_QUERY_TOOLS
    assert len(names) == len(set(names))
    assert OBJECT_QUERY_TOOLS <= {tool.name for tool in get_mcp_tools()}


def test_object_get_requires_current_blender_name():
    tool = {tool.name: tool for tool in get_object_query_tools()}["object_get"]

    assert tool.inputSchema["required"] == ["name"]
    assert tool.inputSchema["properties"]["name"]["type"] == "string"


def test_object_list_is_explicitly_bounded():
    tool = {tool.name: tool for tool in get_object_query_tools()}["object_list"]
    limit = tool.inputSchema["properties"]["limit"]

    assert limit["default"] == 200
    assert limit["maximum"] == 1000


def test_object_capability_claims_match_public_tools():
    for semantic in ("list", "get", "count"):
        capability = provider_contract.CAPABILITIES[f"common.object.{semantic}"]
        assert capability["supported"] is True
        assert capability["mode"] == "native"
