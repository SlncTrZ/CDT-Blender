"""Provider runtime-context tests.
Wing: blender | Topic: capability-honesty | Updated: 2026-09-14 16:50
"""

from __future__ import annotations

from blender_mcp_bridge.tools import get_mcp_tools, provider


def test_runtime_context_fails_closed_when_addon_is_unreachable(monkeypatch):
    monkeypatch.setattr(
        provider,
        "_addon_probe",
        lambda: {"connected": False, "host": "127.0.0.1", "port": 8888},
    )

    snapshot = provider._runtime_context_snapshot()

    assert snapshot == {
        "backend_available": False,
        "context_available": False,
        "reason": "addon_unreachable",
    }


def test_runtime_context_unwraps_native_snapshot(monkeypatch):
    native = {
        "blender_version": "4.5.3 LTS",
        "background": False,
        "ui_available": True,
        "view3d_available": True,
        "active_mode": "OBJECT",
        "active_object": {"name": "Cube", "type": "MESH"},
        "mesh_editable": False,
        "sculpt_context_available": False,
        "render_engine": "BLENDER_EEVEE_NEXT",
    }

    class FakeBlender:
        def send_command(self, command_type, params=None, rid="unknown", timeout_seconds=120.0):
            assert command_type == "get_runtime_context"
            assert params == {}
            assert timeout_seconds == 2.0
            return {"status": "success", "result": native}

    monkeypatch.setattr(
        provider,
        "_addon_probe",
        lambda: {"connected": True, "host": "127.0.0.1", "port": 8888},
    )
    monkeypatch.setattr(provider, "blender", FakeBlender())

    snapshot = provider._runtime_context_snapshot()

    assert snapshot["backend_available"] is True
    assert snapshot["context_available"] is True
    assert snapshot["blender_version"] == "4.5.3 LTS"
    assert snapshot["active_object"] == {"name": "Cube", "type": "MESH"}


def test_system_capabilities_exposes_runtime_context(monkeypatch):
    runtime = {
        "backend_available": True,
        "context_available": True,
        "blender_version": "4.5.3 LTS",
        "background": True,
        "ui_available": False,
    }
    monkeypatch.setattr(provider, "_runtime_context_snapshot", lambda: runtime)

    payload = provider.handle_system_capabilities({})

    assert payload["runtime_context"] == runtime
    assert payload["capabilities"]


def test_runtime_context_command_is_internal_not_public_mcp_tool():
    assert "get_runtime_context" not in {tool.name for tool in get_mcp_tools()}
