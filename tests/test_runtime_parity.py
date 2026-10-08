"""B3/B4 parity tests: local vs remote (agent loopback) behavioral equivalence.

Wing: code | Topic: migration-b3-b4-parity | Updated: 2026-10-07 14:35

Both paths sit on ONE shared fake addon (one Blender): the local adapter
wraps it directly, the workstation agent wraps a second local adapter over
the same fake, and the remote adapter reaches it through the agent over
loopback HTTP. Parity = same typed shapes, same state effects, same
uncertainty fencing on both paths.
"""

from __future__ import annotations

import importlib.util
import sys
import time
import types
from pathlib import Path

import pytest

from blender_mcp_bridge.connection import BlenderConnection
from blender_mcp_bridge.local_runtime import LocalBlenderRuntimeAdapter
from blender_mcp_bridge.remote_runtime import RemoteBlenderRuntimeAdapter
from blender_mcp_bridge.runtime_port import BlenderRuntimePort
from blender_mcp_bridge.runtime_transport import (
    LocalBlenderRuntimeTransport,
    RemoteBlenderRuntimeTransport,
    RuntimeAuthError,
    RuntimeGenerationMismatchError,
    RuntimeOpRefusedError,
    RuntimeTransportError,
    RuntimeUnavailableError,
    RuntimeUncertainError,
)
from blender_mcp_bridge.workstation_agent import (
    WorkstationAgentConfig,
    WorkstationBlenderRuntimeAgent,
)

TOKEN = "parity-token-b4"
ROOT = Path(__file__).resolve().parents[1]


class FakeAddon(BlenderConnection):
    """One stateful fake Blender: objects + context + scripted faults."""

    def __init__(self):
        self.calls: list[dict] = []
        self.objects: dict[str, dict] = {"Cube": {"name": "Cube", "type": "MESH"}}
        self.context: dict = {
            "blender_version_tuple": [4, 5, 3],
            "platform_system": "Windows",
            "background": False,
            "active_mode": "OBJECT",
            "active_object": {"name": "Cube", "type": "MESH"},
        }
        self.sleep_seconds = 0.0

    def send_command(
        self, command_type, params=None, rid="unknown", timeout_seconds=120.0, op_id=None
    ):
        params = params or {}
        self.calls.append({"op": command_type, "params": dict(params), "op_id": op_id})
        if self.sleep_seconds:
            time.sleep(self.sleep_seconds)
        if params.get("force") == "timeout":
            return {
                "status": "error",
                "kind": "timeout_uncertain",
                "retryable": True,
                "op_id": op_id or rid,
                "message": "timed out; call reconcile_operation before retrying.",
            }
        if params.get("force") == "conflict":
            return {
                "status": "error",
                "kind": "payload_conflict",
                "retryable": False,
                "op_id": op_id or rid,
                "message": "different payload fingerprint.",
            }
        if command_type == "get_runtime_context":
            return {"status": "success", "result": dict(self.context)}
        if command_type == "document_info":
            return {
                "status": "success",
                "result": {"name": "Scene", "object_count": len(self.objects)},
            }
        if command_type == "object_list":
            return {"status": "success", "result": list(self.objects.values())}
        if command_type == "object_count":
            return {"status": "success", "result": len(self.objects)}
        if command_type == "object_get":
            name = params.get("name")
            if name in self.objects:
                return {"status": "success", "result": self.objects[name]}
            return {"status": "error", "kind": "not_found", "message": f"{name} missing"}
        if command_type == "get_scene_info":
            return {
                "status": "success",
                "result": {"name": "Scene", "objects": sorted(self.objects)},
            }
        if command_type == "create_cube":
            name = params.get("name", f"Cube.{len(self.objects):03d}")
            self.objects[name] = {"name": name, "type": "MESH"}
            return {"status": "success", "result": {"name": name}, "op_id": op_id or rid}
        if command_type == "object_move":
            name = params.get("name")
            if name in self.objects:
                self.objects[name] = {**self.objects[name], "moved": True}
                return {"status": "success", "result": self.objects[name]}
            return {"status": "error", "kind": "not_found", "message": f"{name} missing"}
        if command_type in ("reconcile_operation", "operation_status"):
            return {"status": "success", "result": {"op_id": params.get("op_id")}}
        return {"status": "success", "result": {"echo": command_type}}


@pytest.fixture()
def _dummy_addon_socket(monkeypatch):
    """Dumb loopback listener so the real socket probe in status/health passes.

    Accepts and closes; speaks no addon protocol (runtime_status/context go
    through the shared FakeAddon, exactly like the real split of probe vs
    command channel).
    """
    import socket as _socket
    import threading

    from blender_mcp_bridge import local_runtime

    srv = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
    srv.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(16)
    port = srv.getsockname()[1]
    stop = threading.Event()

    def _serve():
        while not stop.is_set():
            try:
                srv.settimeout(0.2)
                conn, _ = srv.accept()
            except OSError:
                break
            try:
                conn.close()
            except OSError:
                pass

    thread = threading.Thread(target=_serve, daemon=True)
    thread.start()
    monkeypatch.setattr(local_runtime.settings, "addon_host", "127.0.0.1")
    monkeypatch.setattr(local_runtime.settings, "addon_port", port)
    yield port
    stop.set()
    srv.close()
    thread.join(timeout=2.0)


@pytest.fixture()
def parity(_dummy_addon_socket):
    """Shared addon + local path + agent-backed remote path (started, pinned)."""
    addon = FakeAddon()
    local = LocalBlenderRuntimeTransport(LocalBlenderRuntimeAdapter(addon))
    agent_adapter = LocalBlenderRuntimeAdapter(addon)
    agent = WorkstationBlenderRuntimeAgent(agent_adapter, WorkstationAgentConfig(auth_token=TOKEN))
    agent.start()
    try:
        transport = RemoteBlenderRuntimeTransport(agent.base_url, TOKEN)
        remote = RemoteBlenderRuntimeAdapter(transport)
        remote.pin_generation(agent.generation)
        yield {
            "addon": addon,
            "local": local,
            "remote": remote,
            "agent": agent,
            "transport": transport,
        }
    finally:
        agent.stop()


def test_both_adapters_satisfy_port(parity):
    assert isinstance(parity["local"]._runtime, BlenderRuntimePort)
    assert isinstance(parity["remote"], BlenderRuntimePort)


def test_parity_status_reachable(parity):
    local_status = parity["local"]._runtime.status()
    remote_status = parity["remote"].status()
    assert local_status["status"] == "ok"
    assert remote_status["status"] == "ok"
    assert local_status["addon"]["connected"] is True
    assert remote_status["addon"]["connected"] is True


def test_parity_runtime_context_identity(parity):
    left = parity["local"]._runtime.runtime_status()
    right = parity["remote"].runtime_status()
    for key in ("backend_available", "context_available", "active_mode", "active_object"):
        assert left[key] == right[key], key


def test_parity_reads(parity):
    for op, params in (
        ("document_info", {}),
        ("object_list", {}),
        ("object_get", {"name": "Cube"}),
        ("object_count", {}),
        ("get_scene_info", {}),
        ("get_runtime_context", {}),
    ):
        left = parity["local"].call(op, params)
        right = parity["remote"].execute(op, params)
        assert left == right, op


def test_parity_modeling_op_same_state_effect(parity):
    left = parity["local"].call("create_cube", {"name": "ParityCube"}, op_id="op-par")
    right = parity["remote"].execute("create_cube", {"name": "ParityCube2"}, op_id="op-par2")
    assert left["result"]["name"] == "ParityCube"
    assert right["result"]["name"] == "ParityCube2"
    moved_left = parity["local"].call("object_move", {"name": "ParityCube"})
    moved_right = parity["remote"].execute("object_move", {"name": "ParityCube2"})
    assert moved_left["result"]["moved"] is True
    assert moved_right["result"]["moved"] is True
    assert parity["addon"].objects["ParityCube"]["moved"] is True
    assert parity["addon"].objects["ParityCube2"]["moved"] is True


def test_parity_capabilities_equal(parity):
    assert (
        parity["local"]._runtime.capabilities()["capabilities"]
        == parity["remote"].capabilities()["capabilities"]
    )


def test_parity_queued_timeout_shape(parity):
    left = parity["local"].call("create_cube", {"force": "timeout"}, op_id="op-t")
    right = parity["remote"].execute("create_cube", {"force": "timeout"}, op_id="op-t")
    for out in (left, right):
        assert out["status"] == "error"
        assert out["kind"] == "timeout_uncertain"
        assert out["retryable"] is True
        assert out["op_id"] == "op-t"


def test_parity_context_change_visible_both_paths(parity):
    parity["addon"].context["active_mode"] = "EDIT_MESH"
    assert parity["local"]._runtime.runtime_status()["active_mode"] == "EDIT_MESH"
    assert parity["remote"].runtime_status()["active_mode"] == "EDIT_MESH"


def test_parity_payload_conflict_not_retried_locally(parity):
    before = len(parity["addon"].calls)
    out = parity["remote"].execute("create_cube", {"force": "conflict"}, op_id="op-c")
    assert out["kind"] == "payload_conflict" and out["retryable"] is False
    assert len(parity["addon"].calls) == before + 1  # exactly one attempt


def test_parity_connection_loss_reports_unavailable(parity):
    from blender_mcp_bridge.server import _runtime_error_result

    parity["agent"].stop()
    with pytest.raises(RuntimeUnavailableError):
        parity["remote"].execute("object_list")
    mapped = _runtime_error_result(RuntimeUnavailableError("agent is down"), op_id=None, rid="R1")
    assert mapped["kind"] == "provider_unavailable" and mapped["retryable"] is True
    # provider itself stays reachable: local identity reads keep answering
    assert parity["local"].health()["transport"] == "local"


def test_parity_uncertain_completion_single_attempt_no_replay(parity):
    parity["addon"].sleep_seconds = 5.0
    before = len(parity["addon"].calls)
    try:
        with pytest.raises(RuntimeUncertainError):
            parity["remote"].execute(
                "create_cube", {"name": "Slow"}, op_id="op-slow", timeout_seconds=0.5
            )
    finally:
        parity["addon"].sleep_seconds = 0.0
    time.sleep(0.5)  # let any hidden retry show itself
    attempts = [c for c in parity["addon"].calls[before:] if c["op_id"] == "op-slow"]
    assert len(attempts) == 1  # one dispatch, zero blind replays


def test_server_error_mapping_shapes():
    from blender_mcp_bridge.server import _runtime_error_result

    cases = [
        (RuntimeUnavailableError("down"), "provider_unavailable", True),
        (RuntimeUncertainError("lost"), "timeout_uncertain", True),
        (RuntimeAuthError("bad"), "authentication_error", False),
        (RuntimeGenerationMismatchError("stale"), "conflict", False),
        (RuntimeOpRefusedError("nope"), "validation_error", False),
        (RuntimeTransportError("boom"), "internal_error", False),
    ]
    for exc, kind, retryable in cases:
        out = _runtime_error_result(exc, op_id="op-x", rid="R9")
        assert out["kind"] == kind, kind
        assert out["retryable"] is retryable, kind
        assert out["op_id"] == "op-x", kind
        assert out["status"] == "error", kind


# -- addon LAN-bind refusal (stubbed bpy, no Blender required) --


class _FakeSocket:
    def __init__(self, *args, **kwargs):
        self.bound = None

    def setsockopt(self, *args):
        return None

    def bind(self, address):
        self.bound = address

    def listen(self, _backlog):
        return None

    def close(self):
        return None

    def settimeout(self, timeout):
        return None

    def accept(self):
        raise TimeoutError


def _load_addon_server(monkeypatch):
    timers = types.SimpleNamespace(
        registered=set(),
        register_calls=[],
        register=lambda function, **kwargs: timers.register_calls.append(function),
        unregister=lambda function: None,
        is_registered=lambda function: False,
    )
    bpy = types.SimpleNamespace(app=types.SimpleNamespace(timers=timers))
    monkeypatch.setitem(sys.modules, "bpy", bpy)

    package = types.ModuleType("blender_mcp_addon")
    package.__path__ = [str(ROOT / "blender_mcp_addon")]
    monkeypatch.setitem(sys.modules, "blender_mcp_addon", package)

    for name, class_name in {
        "animation": "AnimationTools",
        "camera": "CameraTools",
        "collections": "CollectionTools",
        "document": "DocumentTools",
        "history": "HistoryTools",
        "interchange": "InterchangeTools",
        "lighting": "LightTools",
        "materials": "MaterialTools",
        "object_query": "ObjectQueryTools",
        "printing": "PrintingTools",
        "rendering": "RenderingTools",
        "scene": "SceneTools",
        "sculpting": "SculptingTools",
    }.items():
        module = types.ModuleType(f"blender_mcp_addon.tools.{name}")
        setattr(module, class_name, type(class_name, (), {}))
        monkeypatch.setitem(sys.modules, module.__name__, module)

    modeling = types.ModuleType("blender_mcp_addon.tools.modeling")
    setattr(modeling, "ModelingTools", type("ModelingTools", (), {}))  # noqa: B010
    monkeypatch.setitem(sys.modules, modeling.__name__, modeling)

    utils = types.ModuleType("blender_mcp_addon.utils")
    setattr(utils, "DEFAULT_HOST", "127.0.0.1")  # noqa: B010
    setattr(utils, "DEFAULT_PORT", 8888)  # noqa: B010
    monkeypatch.setitem(sys.modules, utils.__name__, utils)

    spec = importlib.util.spec_from_file_location(
        "blender_mcp_addon.server", ROOT / "blender_mcp_addon" / "server.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


def test_addon_refuses_lan_bind_without_opt_in(monkeypatch):
    module = _load_addon_server(monkeypatch)
    created: list[_FakeSocket] = []
    monkeypatch.setattr(
        module.socket, "socket", lambda *a, **k: created.append(_FakeSocket()) or created[-1]
    )

    server = module.BlenderMCPServer()
    result = server.start_server(host="0.0.0.0", port=8888)
    assert result["ok"] is False
    assert result["state"] == "refused"
    assert created == []  # no socket ever bound
    assert server.running is False


def test_addon_loopback_bind_still_allowed(monkeypatch):
    module = _load_addon_server(monkeypatch)
    created: list[_FakeSocket] = []
    monkeypatch.setattr(
        module.socket, "socket", lambda *a, **k: created.append(_FakeSocket()) or created[-1]
    )

    server = module.BlenderMCPServer()
    result = server.start_server(host="127.0.0.1", port=8888)
    assert result["ok"] is True
    assert created and created[0].bound == ("127.0.0.1", 8888)
    server.stop_server()
