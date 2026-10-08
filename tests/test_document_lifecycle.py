"""Document lifecycle contract tests.
Wing: blender | Topic: document-lifecycle | Updated: 2026-09-14 17:02
"""

from __future__ import annotations

from blender_mcp_bridge import provider_contract
from blender_mcp_bridge.tools import get_mcp_tools
from blender_mcp_bridge.tools.document import get_document_tools

DOCUMENT_TOOLS = {
    "document_new",
    "document_open",
    "document_info",
    "document_save",
    "document_save_as",
    "document_close",
}


def test_document_tools_are_public_and_unique():
    document = get_document_tools()
    names = [tool.name for tool in document]

    assert set(names) == DOCUMENT_TOOLS
    assert len(names) == len(set(names))
    assert DOCUMENT_TOOLS <= {tool.name for tool in get_mcp_tools()}


def test_document_paths_are_explicit_in_schema():
    tools = {tool.name: tool for tool in get_document_tools()}

    for name in ("document_open", "document_save_as"):
        assert tools[name].inputSchema["required"] == ["filepath"]
        assert tools[name].inputSchema["properties"]["filepath"]["type"] == "string"


def test_document_capability_claims_match_public_tools():
    for semantic in ("new", "open", "info", "save", "save_as", "close"):
        capability = provider_contract.CAPABILITIES[f"common.document.{semantic}"]
        assert capability["supported"] is True
        assert capability["mode"] == "native"
