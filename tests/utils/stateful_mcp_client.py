# tests/utils/stateful_mcp_client.py
"""Test adapter: re-exports the stateful MCP client from the package.

Production clients moved to ``blender_mcp_bridge.client`` (H11) so installed
playback does not depend on ``tests.utils``. This module keeps the old import
path working for tests/scenarios without shipping test code in the wheel.
"""

from blender_mcp_bridge.client import StatefulMCPClient  # noqa: F401

__all__ = ["StatefulMCPClient"]
