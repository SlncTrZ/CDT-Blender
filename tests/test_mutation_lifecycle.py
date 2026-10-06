"""Unit and integration tests for mutation lifecycle (BL-01 + BL-02)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import threading
import time
import types
import pytest

ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = ROOT / "blender_mcp_addon" / "server.py"
LIFECYCLE_PATH = ROOT / "blender_mcp_addon" / "lifecycle.py"

# Load lifecycle directly without triggering package __init__.py
spec_lc = importlib.util.spec_from_file_location("blender_mcp_addon.lifecycle", LIFECYCLE_PATH)
assert spec_lc is not None and spec_lc.loader is not None
lifecycle_mod = importlib.util.module_from_spec(spec_lc)
sys.modules["blender_mcp_addon.lifecycle"] = lifecycle_mod
spec_lc.loader.exec_module(lifecycle_mod)

MutationLifecycleManager = lifecycle_mod.MutationLifecycleManager
ReceiptState = lifecycle_mod.ReceiptState


class FakeTimers:
    def __init__(self) -> None:
        self.registered: set[object] = set()

    def register(self, function, **kwargs):
        self.registered.add(function)

    def unregister(self, function):
        self.registered.remove(function)

    def is_registered(self, function) -> bool:
        return function in self.registered


def _load_server_module(monkeypatch):
    timers = FakeTimers()
    bpy = types.SimpleNamespace(
        app=types.SimpleNamespace(timers=timers, version_string="4.5.3", version=(4, 5, 3), background=True),
        context=types.SimpleNamespace(active_object=None, mode="OBJECT", window_manager=None, scene=None),
        data=types.SimpleNamespace(objects={}, filepath=""),
    )
    monkeypatch.setitem(sys.modules, "bpy", bpy)

    package = types.ModuleType("blender_mcp_addon")
    package.__path__ = [str(ROOT / "blender_mcp_addon")]
    monkeypatch.setitem(sys.modules, "blender_mcp_addon", package)

    for name in (
        "animation",
        "camera",
        "collections",
        "document",
        "history",
        "interchange",
        "lighting",
        "materials",
        "object_query",
        "printing",
        "rendering",
        "scene",
        "sculpting",
    ):
        module = types.ModuleType(f"blender_mcp_addon.tools.{name}")
        class_name = {
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
        }[name]
        setattr(module, class_name, type(class_name, (), {}))
        monkeypatch.setitem(sys.modules, module.__name__, module)

    modeling = types.ModuleType("blender_mcp_addon.tools.modeling")
    setattr(modeling, "ModelingTools", type("ModelingTools", (), {}))
    monkeypatch.setitem(sys.modules, modeling.__name__, modeling)

    utils = types.ModuleType("blender_mcp_addon.utils")
    setattr(utils, "DEFAULT_HOST", "127.0.0.1")
    setattr(utils, "DEFAULT_PORT", 8888)
    monkeypatch.setitem(sys.modules, utils.__name__, utils)

    spec = importlib.util.spec_from_file_location("blender_mcp_addon.server", SERVER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


def test_lifecycle_manager_idempotency():
    mgr = MutationLifecycleManager()
    op_id = "op-uuid-1"

    rejection = mgr.check_admission("create_cube", op_id)
    assert rejection is None

    mgr.record_pending(op_id, "create_cube", {}, time.monotonic() + 10)
    mgr.record_in_flight(op_id)
    mgr.record_committed(op_id, {"status": "success", "name": "Cube"})

    rejection2 = mgr.check_admission("create_cube", op_id)
    assert rejection2 is not None
    assert rejection2["status"] == "success"
    assert rejection2["cached"] is True
    assert rejection2["op_id"] == op_id


def test_lifecycle_uncertain_predecessor_gating():
    mgr = MutationLifecycleManager()
    op1 = "op-uncertain-1"
    op2 = "op-dependent-2"

    mgr.record_uncertain(op1, "Timeout while baking", cmd_type="create_cube")
    assert mgr.has_uncertain() is True

    rej = mgr.check_admission("object_move", op2)
    assert rej is not None
    assert rej["status"] == "error"
    assert rej["kind"] == "uncertain_predecessor_blocked"
    assert op1 in rej["uncertain_operations"]

    rej_query = mgr.check_admission("object_list", "op-query")
    assert rej_query is None

    rec = mgr.reconcile(op1, action="acknowledge")
    assert rec["status"] == "success"
    assert mgr.has_uncertain() is False

    rej2 = mgr.check_admission("object_move", op2)
    assert rej2 is None


def test_server_op_id_idempotency_avoids_duplicate_side_effect(monkeypatch):
    module = _load_server_module(monkeypatch)
    server = module.BlenderMCPServer()
    server.running = True

    call_count = 0

    def mock_exec(cmd):
        nonlocal call_count
        call_count += 1
        return {"status": "success", "result": {"name": "TestCube"}}

    monkeypatch.setattr(server, "execute_command", mock_exec)

    res1 = None
    op_id = "op-idem-1"

    def run_cmd():
        nonlocal res1
        res1 = server.handle_command({"type": "create_cube", "op_id": op_id, "params": {}})

    t = threading.Thread(target=run_cmd)
    t.start()
    time.sleep(0.02)
    server._process_queue()
    t.join(timeout=1.0)

    assert res1 is not None
    assert call_count == 1
    assert server.lifecycle.get_receipt(op_id)["state"] == ReceiptState.COMMITTED

    res2 = server.handle_command({"type": "create_cube", "op_id": op_id, "params": {}})
    assert res2["status"] == "success"
    assert res2["cached"] is True
    assert call_count == 1


def test_server_expired_pending_command_never_starts(monkeypatch):
    module = _load_server_module(monkeypatch)
    server = module.BlenderMCPServer()
    server.running = True

    executed = False

    def mock_exec(cmd):
        nonlocal executed
        executed = True
        return {"status": "success"}

    monkeypatch.setattr(server, "execute_command", mock_exec)

    op_id = "op-expired-pending"
    now = time.monotonic()
    container = {"result": None, "op_id": op_id, "dispatched": False}
    ev = threading.Event()

    server.command_queue.put(
        {
            "command": {"type": "create_cube", "op_id": op_id},
            "event": ev,
            "container": container,
            "op_id": op_id,
            "deadline": now - 1.0,
            "cmd_type": "create_cube",
        }
    )

    server._process_queue()

    assert executed is False
    assert container["result"]["kind"] == "expired_pending"
    receipt = server.lifecycle.get_receipt(op_id)
    assert receipt["state"] == ReceiptState.EXPIRED_PENDING


def test_server_started_timeout_becomes_uncertain(monkeypatch):
    module = _load_server_module(monkeypatch)
    server = module.BlenderMCPServer()
    server.running = True

    def slow_exec(cmd):
        time.sleep(0.1)
        return {"status": "success", "result": {"name": "Done"}}

    monkeypatch.setattr(server, "execute_command", slow_exec)

    op_id = "op-timeout-uncertain"
    res = None

    def run_cmd():
        nonlocal res
        res = server.handle_command({
            "type": "create_cube",
            "op_id": op_id,
            "timeout": 0.03,
            "params": {},
        })

    t = threading.Thread(target=run_cmd)
    t.start()

    time.sleep(0.01)
    t_tick = threading.Thread(target=server._process_queue)
    t_tick.start()

    t.join(timeout=1.0)
    t_tick.join(timeout=1.0)

    assert res is not None
    assert res["status"] == "error"
    assert res["kind"] == "timeout_uncertain"
    assert op_id in server.lifecycle.get_uncertain_ops()

    dep_res = server.handle_command({
        "type": "object_move",
        "op_id": "op-blocked-write",
        "params": {"delta_x": 1.0},
    })
    assert dep_res["status"] == "error"
    assert dep_res["kind"] == "uncertain_predecessor_blocked"

    rec_res = server.reconcile_operation(op_id, action="acknowledge")
    assert rec_res["status"] == "success"
    assert op_id not in server.lifecycle.get_uncertain_ops()
