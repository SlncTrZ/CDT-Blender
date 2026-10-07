"""B2 transport/agent tests: allowlist, auth, generation, loopback, uncertainty.

Wing: code | Topic: migration-b2-transport | Updated: 2026-10-07 14:20
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

import pytest

from blender_mcp_bridge.local_runtime import LocalBlenderRuntimeAdapter
from blender_mcp_bridge.runtime_port import BlenderRuntimePort
from blender_mcp_bridge.runtime_transport import (
    ALLOWED_OPS,
    READ_ONLY_OPS,
    LocalBlenderRuntimeTransport,
    RemoteBlenderRuntimeTransport,
    RuntimeGenerationMismatchError,
    RuntimeOpRefusedError,
    RuntimeTransportError,
    RuntimeUnavailableError,
    RuntimeUncertainError,
    bearer_matches,
    check_op,
    check_request_size,
    check_timeout_ms,
    is_mutation_op,
)
from blender_mcp_bridge.workstation_agent import (
    WorkstationAgentConfig,
    WorkstationBlenderRuntimeAgent,
)

TOKEN = "test-token-b2"


class FakeAdapter:
    """In-memory B1 port: scripted results, counted dispatches, no sockets."""

    def __init__(self, handler=None):
        self.calls: list[dict] = []
        self.handler = handler or (lambda op, params, rid, timeout, op_id: {"status": "ok"})

    @property
    def backend(self):
        return object()

    def execute(self, op, params=None, *, rid="unknown", timeout_seconds=120.0, op_id=None):
        self.calls.append({"op": op, "params": params, "rid": rid, "op_id": op_id})
        return self.handler(op, params, rid, timeout_seconds, op_id)

    def capabilities(self):
        return {"provider_name": "blender"}

    def status(self):
        return {"status": "ok"}

    def runtime_status(self):
        return {"backend_available": True, "context_available": True}

    def health(self):
        return {"transport": "local", "reachable": True}


def test_fake_adapter_satisfies_port():
    assert isinstance(FakeAdapter(), BlenderRuntimePort)


def test_wired_mcp_tools_are_all_allowlisted():
    from blender_mcp_bridge.server import _answer_locally
    from blender_mcp_bridge.tools import get_mcp_tools

    wired = [t.name for t in get_mcp_tools() if _answer_locally(t.name, {}) is None]
    missing = [name for name in wired if name not in ALLOWED_OPS]
    assert missing == []
    assert len(ALLOWED_OPS) >= len(wired)


def test_mutation_rule_mirrors_addon_lifecycle():
    # Spot-check against blender_mcp_addon/lifecycle.py READ_ONLY_COMMANDS.
    for op in READ_ONLY_OPS:
        assert not is_mutation_op(op), op
    for op in (
        "create_cube",
        "object_move",
        "document_save",
        "undo",
        "redo",
        "enter_sculpt_mode",
        "render_frame",
    ):
        assert is_mutation_op(op), op
    assert not is_mutation_op("get_scene_info")
    assert not is_mutation_op("")


def test_check_op_refuses_unknown_before_dispatch():
    with pytest.raises(RuntimeOpRefusedError):
        check_op("exec_python_evil")
    assert check_op("create_cube") == "create_cube"


def test_deadline_and_size_bounds():
    with pytest.raises(ValueError):
        check_timeout_ms(50)
    with pytest.raises(ValueError):
        check_timeout_ms(10_000_000)
    assert check_timeout_ms(None) > 0
    with pytest.raises(RuntimeOpRefusedError):
        check_request_size({"op": "x", "pad": "y" * (1024 * 1024 + 1)})


def test_bearer_matches_never_matches_empty_expected():
    assert bearer_matches("abc", "abc")
    assert not bearer_matches("abc", "abd")
    assert not bearer_matches("abc", "")


def test_local_transport_delegates_and_health():
    fake_conn_calls: list[dict] = []

    class Conn:
        def send_command(self, op, params=None, rid="unknown", timeout_seconds=120.0, op_id=None):
            fake_conn_calls.append({"op": op})
            return {"status": "success", "result": {"echo": op}}

    from blender_mcp_bridge.connection import BlenderConnection

    class FakeConn(BlenderConnection):
        def send_command(self, *args, **kwargs):
            return Conn().send_command(*args, **kwargs)

    transport = LocalBlenderRuntimeTransport(LocalBlenderRuntimeAdapter(FakeConn()))
    assert transport.call("object_list", {"a": 1}) == {
        "status": "success",
        "result": {"echo": "object_list"},
    }
    assert transport.health()["transport"] == "local"
    transport.close()
    with pytest.raises(RuntimeUnavailableError):
        transport.call("object_list")


def test_local_transport_generation_mismatch_discards():
    from blender_mcp_bridge.connection import BlenderConnection

    class FakeConn(BlenderConnection):
        def send_command(self, *args, **kwargs):
            return {"status": "ok"}

    transport = LocalBlenderRuntimeTransport(LocalBlenderRuntimeAdapter(FakeConn()))
    with pytest.raises(RuntimeGenerationMismatchError):
        transport.call("object_list", expected_generation="gen-stale")


def test_remote_transport_constructor_guards():
    with pytest.raises(ValueError):
        RemoteBlenderRuntimeTransport("http://127.0.0.1:1", "")
    with pytest.raises(RuntimeOpRefusedError):
        RemoteBlenderRuntimeTransport("http://192.168.1.50:9999", TOKEN)
    assert "redacted" in repr(RemoteBlenderRuntimeTransport("http://127.0.0.1:1", TOKEN))


def test_agent_constructor_guards():
    with pytest.raises(ValueError):
        WorkstationAgentConfig(auth_token="")
    with pytest.raises(ValueError):
        WorkstationAgentConfig(host="0.0.0.0", auth_token=TOKEN)
    with pytest.raises(TypeError):
        WorkstationBlenderRuntimeAgent(object(), WorkstationAgentConfig(auth_token=TOKEN))


def test_agent_holds_no_lifecycle_authority():
    import pathlib

    src = (
        pathlib.Path(__file__)
        .resolve()
        .parents[1]
        .joinpath("blender_mcp_bridge", "workstation_agent.py")
        .read_text(encoding="utf-8")
    )
    # The agent documents the addon authority by name but must never bind it:
    # no import, no instantiation, no shared state.
    assert "from .lifecycle" not in src
    assert "import lifecycle" not in src
    assert "MutationLifecycleManager(" not in src


def _started_agent(adapter, **cfg_overrides):
    config = WorkstationAgentConfig(auth_token=TOKEN, **cfg_overrides)
    agent = WorkstationBlenderRuntimeAgent(adapter, config)
    url = agent.start()
    assert url.startswith("http://127.0.0.1:")
    return agent


def _authed_get(agent, path):
    req = urllib.request.Request(
        f"{agent.base_url}{path}", headers={"Authorization": f"Bearer {TOKEN}"}
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return resp.status, json.loads(resp.read().decode())


def test_agent_heartbeat_and_generation():
    agent = _started_agent(FakeAdapter())
    try:
        status, body = _authed_get(agent, "/health")
        assert status == 200 and body["ok"] is True
        beat = body["result"]
        assert beat["generation"] == agent.generation
        assert beat["generation"].startswith("gen-")
        assert beat["session"]["pid"] > 0
    finally:
        agent.stop()


def test_agent_restart_mints_new_generation():
    adapter = FakeAdapter()
    first = _started_agent(adapter)
    gen_a = first.generation
    first.stop()
    second = _started_agent(adapter)
    try:
        assert second.generation != gen_a
    finally:
        second.stop()


def test_agent_rejects_bad_credentials():
    agent = _started_agent(FakeAdapter())
    try:
        req = urllib.request.Request(
            f"{agent.base_url}/health", headers={"Authorization": "Bearer wrong"}
        )
        with pytest.raises(urllib.error.HTTPError) as excinfo:
            urllib.request.urlopen(req, timeout=5)
        assert excinfo.value.code == 401
    finally:
        agent.stop()


def test_agent_refuses_unknown_op_before_adapter():
    adapter = FakeAdapter()
    agent = _started_agent(adapter)
    try:
        out = agent.dispatch("exec_python_evil", {})
        assert out["ok"] is False and out["error_code"] == "unknown_op"
        assert adapter.calls == []
    finally:
        agent.stop()


def test_agent_refuses_stale_generation_before_adapter():
    adapter = FakeAdapter()
    agent = _started_agent(adapter)
    try:
        out = agent.dispatch("create_cube", {}, expected_generation="gen-stale")
        assert out["ok"] is False and out["error_code"] == "generation_mismatch"
        assert adapter.calls == []
    finally:
        agent.stop()


def test_remote_loopback_round_trip_with_generation_pin():
    adapter = FakeAdapter(
        handler=lambda op, params, rid, timeout, op_id: {
            "status": "success",
            "result": {"echo": op},
            "op_id": op_id,
        }
    )
    agent = _started_agent(adapter)
    try:
        transport = RemoteBlenderRuntimeTransport(agent.base_url, TOKEN)
        assert transport.health()["generation"] == agent.generation
        from blender_mcp_bridge.remote_runtime import RemoteBlenderRuntimeAdapter

        remote = RemoteBlenderRuntimeAdapter(transport)
        remote.pin_generation(agent.generation)
        out = remote.execute("create_cube", {"size": 1.0}, rid="R1", op_id="op-1")
        assert out == {"status": "success", "result": {"echo": "create_cube"}, "op_id": "op-1"}
        assert adapter.calls[0]["op"] == "create_cube"
        # stale pin discards before trusting results
        remote.pin_generation("gen-stale")
        with pytest.raises(RuntimeGenerationMismatchError):
            remote.execute("object_list")
    finally:
        agent.stop()


def test_remote_auth_failure_is_typed():
    agent = _started_agent(FakeAdapter())
    try:
        transport = RemoteBlenderRuntimeTransport(agent.base_url, "wrong-token")
        from blender_mcp_bridge import runtime_transport as rt

        with pytest.raises(rt.RuntimeAuthError):
            transport.call("object_list")
    finally:
        agent.stop()


def test_remote_connection_loss_is_unavailable_not_success():
    transport = RemoteBlenderRuntimeTransport("http://127.0.0.1:1", TOKEN)
    with pytest.raises(RuntimeUnavailableError):
        transport.call("object_list")


def test_remote_slow_dispatch_is_uncertain_single_attempt():
    def slow(op, params, rid, timeout, op_id):
        time.sleep(30)
        return {"status": "success"}

    adapter = FakeAdapter(handler=slow)
    agent = _started_agent(adapter)
    try:
        transport = RemoteBlenderRuntimeTransport(agent.base_url, TOKEN)
        with pytest.raises(RuntimeUncertainError):
            transport.call("create_cube", {}, timeout_seconds=0.5, op_id="op-slow")
        # agent eventually ran it at most once; transport never retried.
        time.sleep(0.2)
        assert len(adapter.calls) <= 1
    finally:
        agent.stop()


def test_agent_oversized_body_refused_before_adapter():
    adapter = FakeAdapter()
    agent = _started_agent(adapter, max_request_bytes=64)
    try:
        transport = RemoteBlenderRuntimeTransport(agent.base_url, TOKEN)
        with pytest.raises(RuntimeTransportError):  # 400 oversized, never success
            transport.call("object_list", {"pad": "y" * 4096})
        assert adapter.calls == []
    finally:
        agent.stop()
