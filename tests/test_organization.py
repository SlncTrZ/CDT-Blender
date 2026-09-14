"""Common organization-list contract tests.
Wing: blender | Topic: organization | Updated: 2026-09-14 18:49
"""

from __future__ import annotations

from blender_mcp_bridge import provider_contract
from blender_mcp_bridge.tools import get_mcp_tools
from blender_mcp_bridge.tools.organization import get_organization_tools


def test_organization_list_is_public_and_unique():
    tools = get_organization_tools()
    names = [tool.name for tool in tools]

    assert names == ["organization_list"]
    assert "organization_list" in {tool.name for tool in get_mcp_tools()}


def test_organization_list_is_explicitly_bounded():
    tool = get_organization_tools()[0]
    limit = tool.inputSchema["properties"]["limit"]

    assert limit["default"] == 200
    assert limit["maximum"] == 1000


def test_organization_capability_claim_matches_public_tool():
    capability = provider_contract.CAPABILITIES["common.organization.list"]

    assert capability["supported"] is True
    assert capability["mode"] == "native"
