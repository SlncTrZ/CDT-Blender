"""The addon epoch fences operations when Blender restarts under a live agent."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from blender_mcp_bridge import local_runtime
from blender_mcp_bridge.connection import BlenderConnection
from blender_mcp_bridge.local_runtime import LocalBlenderRuntimeAdapter
from blender_mcp_bridge.workstation_agent import (
    WorkstationAgentConfig,
    WorkstationBlenderRuntimeAgent,
)


class NativeConnection(BlenderConnection):
    def __init__(self):
        self.epoch = "addon-first"
        self.effects = []
        self.restart_before_mutation = False
        self.available = True

    def send_command(
        self, command_type, params=None, rid="unknown", timeout_seconds=120.0, op_id=None
    ):
        params = dict(params or {})
        if command_type == "get_runtime_context":
            if not self.available:
                return {"status": "error", "kind": "provider_unavailable"}
            return {"status": "success", "result": {"runtime_generation": self.epoch}}
        if self.restart_before_mutation:
            self.epoch = "addon-restarted"
        expected = params.get("_runtime_generation")
        if expected is not None and expected != self.epoch:
            return {"status": "error", "kind": "runtime_generation_mismatch"}
        self.effects.append((command_type, params))
        return {"status": "success", "result": {"name": params.get("name")}}


def guarded_agent(monkeypatch):
    monkeypatch.setattr(local_runtime, "_addon_probe", lambda: {"connected": True})
    connection = NativeConnection()
    config = WorkstationAgentConfig(auth_token="fixture-secret")
    config.require_native_generation = True
    return connection, WorkstationBlenderRuntimeAgent(
        LocalBlenderRuntimeAdapter(connection), config
    )


def addon_module(monkeypatch):
    path = Path(__file__).resolve().parent / "test_addon_lifecycle.py"
    spec = importlib.util.spec_from_file_location("addon_test_fixture", path)
    assert spec and spec.loader
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    module, _ = fixture._load_server_module(monkeypatch)
    return module


def test_native_restart_refused_without_second_mutation(monkeypatch):
    native, agent = guarded_agent(monkeypatch)
    first = agent.dispatch("create_cube", {"name": "first"}, op_id="first")
    assert first["ok"] is True and len(native.effects) == 1
    native.epoch = "addon-restarted"
    refused = agent.dispatch("create_cube", {"name": "second"}, op_id="second")
    assert refused["ok"] is False and refused["error_code"] == "generation_mismatch"
    assert refused["completion_unknown"] is False
    assert len(native.effects) == 1
    assert agent.heartbeat()["adapter"]["native_identity_ready"] is False


def test_addon_fence_closes_restart_between_probe_and_native_dispatch(monkeypatch):
    native, agent = guarded_agent(monkeypatch)
    native.restart_before_mutation = True
    response = agent.dispatch("create_cube", {"name": "race"}, op_id="race")
    assert response["ok"] is False and response["error_code"] == "generation_mismatch"
    assert response["completion_unknown"] is False and native.effects == []


def test_caller_cannot_replace_agent_pinned_addon_identity(monkeypatch):
    native, agent = guarded_agent(monkeypatch)
    assert agent.dispatch("create_cube", {"name": "first"}, op_id="first")["ok"]
    native.epoch = "addon-restarted"
    response = agent.dispatch(
        "create_cube", {"name": "second", "_runtime_generation": native.epoch}, op_id="second"
    )
    assert response["error_code"] == "generation_mismatch"
    assert len(native.effects) == 1


def test_unavailable_native_discovery_never_runs_mutation(monkeypatch):
    native, agent = guarded_agent(monkeypatch)
    native.available = False
    response = agent.dispatch("create_cube", {"name": "absent"}, op_id="absent")
    assert response["ok"] is False and response["error_code"] == "unavailable"
    assert native.effects == []


def test_addon_epoch_mismatch_refuses_before_receipt_or_queue(monkeypatch):
    module = addon_module(monkeypatch)
    server = module.BlenderMCPServer()
    server.running = True
    result = server.handle_command(
        {
            "type": "create_cube",
            "params": {"name": "refused", "_runtime_generation": "old"},
            "op_id": "stale-native",
            "timeout": 0.001,
        }
    )
    assert result["kind"] == "runtime_generation_mismatch"
    assert result["retryable"] is False
    assert server.command_queue.empty()
    assert server.lifecycle.get_receipt("stale-native") is None


def test_each_addon_writer_has_a_distinct_epoch(monkeypatch):
    module = addon_module(monkeypatch)
    assert (
        module.BlenderMCPServer().runtime_generation != module.BlenderMCPServer().runtime_generation
    )
