"""B1 runtime-port tests: LocalBlenderRuntimeAdapter 1:1 delegation.

Wing: code | Topic: migration-b1-seam | Updated: 2026-10-07 14:10
"""

from __future__ import annotations

import socket

import pytest

from blender_mcp_bridge import provider_contract as contract
from blender_mcp_bridge.connection import BlenderConnection
from blender_mcp_bridge.local_runtime import LOCAL_GENERATION, LocalBlenderRuntimeAdapter
from blender_mcp_bridge.runtime_port import BlenderRuntimePort


class FakeConnection(BlenderConnection):
    """In-memory stand-in: records calls, never touches a socket."""

    def __init__(self, handler=None):
        self.calls: list[dict] = []
        self.handler = handler or (lambda op, params, rid, timeout, op_id: {"status": "ok"})

    def send_command(
        self, command_type, params=None, rid="unknown", timeout_seconds=120.0, op_id=None
    ):
        self.calls.append(
            {
                "op": command_type,
                "params": params,
                "rid": rid,
                "timeout_seconds": timeout_seconds,
                "op_id": op_id,
            }
        )
        return self.handler(command_type, params, rid, timeout_seconds, op_id)


def _closed_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def test_adapter_satisfies_runtime_port_protocol():
    adapter = LocalBlenderRuntimeAdapter(FakeConnection())
    assert isinstance(adapter, BlenderRuntimePort)


def test_adapter_rejects_non_connection():
    with pytest.raises(TypeError):
        LocalBlenderRuntimeAdapter(object())


def test_execute_delegates_1_to_1_with_same_shapes():
    fake = FakeConnection(
        handler=lambda op, params, rid, timeout, op_id: {
            "status": "success",
            "result": {"name": "Cube"},
            "op_id": op_id,
        }
    )
    adapter = LocalBlenderRuntimeAdapter(fake)
    result = adapter.execute(
        "create_cube", {"size": 2.0}, rid="R1", timeout_seconds=30.0, op_id="op-1"
    )
    assert result == {"status": "success", "result": {"name": "Cube"}, "op_id": "op-1"}
    assert fake.calls == [
        {
            "op": "create_cube",
            "params": {"size": 2.0},
            "rid": "R1",
            "timeout_seconds": 30.0,
            "op_id": "op-1",
        }
    ]


def test_execute_passes_addon_error_dicts_through_untouched():
    addon_error = {
        "status": "error",
        "kind": "timeout_uncertain",
        "retryable": True,
        "op_id": "op-9",
        "message": "timed out; reconcile before retrying.",
    }
    adapter = LocalBlenderRuntimeAdapter(FakeConnection(handler=lambda *a: addon_error))
    assert adapter.execute("create_cube", {}, op_id="op-9") == addon_error


def test_backend_escape_hatch_returns_wrapped_connection():
    fake = FakeConnection()
    adapter = LocalBlenderRuntimeAdapter(fake)
    assert adapter.backend is fake
    assert adapter.generation == LOCAL_GENERATION


def test_capabilities_match_contract_without_addon_contact():
    def explode(*args):
        raise AssertionError("capabilities must not contact the addon")

    adapter = LocalBlenderRuntimeAdapter(FakeConnection(handler=explode))
    caps = adapter.capabilities()
    assert caps["capabilities"] == contract.CAPABILITIES
    assert caps["contract_version"] == contract.CONTRACT_VERSION
    assert caps["provider_name"] == contract.PROVIDER_ID


def test_status_reports_unreachable_addon_without_raising(monkeypatch):
    from blender_mcp_bridge import local_runtime

    monkeypatch.setattr(local_runtime.settings, "addon_port", _closed_port())
    adapter = LocalBlenderRuntimeAdapter(BlenderConnection())
    status = adapter.status()
    assert status["status"] == "ok"  # provider stays reachable
    assert status["transport"] == "local"
    assert status["addon"]["connected"] is False


def test_runtime_status_unreachable_shape(monkeypatch):
    from blender_mcp_bridge import local_runtime

    monkeypatch.setattr(local_runtime.settings, "addon_port", _closed_port())
    adapter = LocalBlenderRuntimeAdapter(BlenderConnection())
    assert adapter.runtime_status() == {
        "backend_available": False,
        "context_available": False,
        "reason": "addon_unreachable",
    }


def _probe_up(monkeypatch):
    from blender_mcp_bridge import local_runtime

    monkeypatch.setattr(
        local_runtime,
        "_addon_probe",
        lambda: {"connected": True, "host": "127.0.0.1", "port": 8888},
    )


def test_runtime_status_shapes_live_context(monkeypatch):
    _probe_up(monkeypatch)
    snapshot = {
        "status": "success",
        "result": {
            "blender_version": "4.5.3 LTS",
            "blender_version_tuple": [4, 5, 3],
            "platform_system": "Windows",
            "background": False,
            "active_mode": "OBJECT",
        },
    }
    adapter = LocalBlenderRuntimeAdapter(FakeConnection(handler=lambda *a: snapshot))
    out = adapter.runtime_status()
    assert out["backend_available"] is True
    assert out["context_available"] is True
    assert out["runtime_support_status"] == "verified_native_baseline"


def test_runtime_status_marks_unverified_runtime(monkeypatch):
    _probe_up(monkeypatch)
    snapshot = {
        "status": "success",
        "result": {"blender_version_tuple": [9, 9, 9], "platform_system": "OtherOS"},
    }
    adapter = LocalBlenderRuntimeAdapter(FakeConnection(handler=lambda *a: snapshot))
    assert adapter.runtime_status()["runtime_support_status"] == "unverified_runtime"


def test_runtime_status_malformed_is_unavailable(monkeypatch):
    _probe_up(monkeypatch)
    adapter = LocalBlenderRuntimeAdapter(
        FakeConnection(handler=lambda *a: {"status": "error", "kind": "timeout"})
    )
    out = adapter.runtime_status()
    assert out["context_available"] is False
    assert out["reason"] == "runtime_context_unavailable"


def test_health_is_read_only_liveness(monkeypatch):
    from blender_mcp_bridge import local_runtime

    monkeypatch.setattr(local_runtime.settings, "addon_port", _closed_port())
    fake = FakeConnection()
    adapter = LocalBlenderRuntimeAdapter(fake)
    health = adapter.health()
    assert health["transport"] == "local"
    assert health["reachable"] is False
    assert health["generation"] == LOCAL_GENERATION
    assert fake.calls == []  # no CAD contact, socket probe only
