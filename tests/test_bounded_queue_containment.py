"""Tests for Bounded execution / backpressure (BL-03) and Path containment (BL-04)."""

import importlib.util
import os
import sys
import tempfile
import threading
import time
import types
from pathlib import Path

import pytest

if "bpy" not in sys.modules:
    sys.modules["bpy"] = types.SimpleNamespace(
        app=types.SimpleNamespace(
            timers=types.SimpleNamespace(
                register=lambda *a, **k: None,
                unregister=lambda *a: None,
                is_registered=lambda *a: False,
            ),
            version_string="4.5.3",
            version=(4, 5, 3),
            background=True,
        ),
        context=types.SimpleNamespace(
            active_object=None,
            mode="OBJECT",
            window_manager=None,
            scene=None,
        ),
        data=types.SimpleNamespace(objects={}, filepath=""),
        types=types.SimpleNamespace(Operator=type("Operator", (), {}), Panel=type("Panel", (), {})),
        utils=types.SimpleNamespace(register_class=lambda c: None, unregister_class=lambda c: None),
    )

ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = ROOT / "blender_mcp_addon" / "server.py"
LIFECYCLE_PATH = ROOT / "blender_mcp_addon" / "lifecycle.py"


def _get_server():
    package = types.ModuleType("blender_mcp_addon")
    package.__path__ = [str(ROOT / "blender_mcp_addon")]
    sys.modules["blender_mcp_addon"] = package

    spec_lc = importlib.util.spec_from_file_location("blender_mcp_addon.lifecycle", LIFECYCLE_PATH)
    assert spec_lc is not None and spec_lc.loader is not None
    lc_mod = importlib.util.module_from_spec(spec_lc)
    sys.modules["blender_mcp_addon.lifecycle"] = lc_mod
    spec_lc.loader.exec_module(lc_mod)

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
        mod = types.ModuleType(f"blender_mcp_addon.tools.{name}")
        cname = {
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
        setattr(mod, cname, type(cname, (), {}))
        sys.modules[mod.__name__] = mod

    modeling = types.ModuleType("blender_mcp_addon.tools.modeling")
    setattr(modeling, "ModelingTools", type("ModelingTools", (), {}))  # noqa: B010
    sys.modules[modeling.__name__] = modeling

    spec = importlib.util.spec_from_file_location("blender_mcp_addon.server", SERVER_PATH)
    assert spec is not None and spec.loader is not None
    smod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = smod
    spec.loader.exec_module(smod)
    return smod


server_mod = _get_server()
BlenderMCPServer = server_mod.BlenderMCPServer
ADMISSION_QUEUE_MAXSIZE = server_mod.ADMISSION_QUEUE_MAXSIZE
MAX_COMMANDS_PER_TICK = server_mod.MAX_COMMANDS_PER_TICK
MAX_ACTIVE_CLIENT_THREADS = server_mod.MAX_ACTIVE_CLIENT_THREADS

from blender_mcp_addon.utils import (  # noqa: E402
    OutsideAllowRoots,
    require_allowed,
)


def test_admission_queue_saturation_rejection():
    server = BlenderMCPServer()
    server.running = True

    events = []
    for i in range(ADMISSION_QUEUE_MAXSIZE):
        ev = threading.Event()
        events.append(ev)
        server.command_queue.put_nowait(
            {
                "command": {"type": "object_list", "op_id": f"q-fill-{i}"},
                "event": ev,
                "container": {"result": None},
                "op_id": f"q-fill-{i}",
                "deadline": time.monotonic() + 10.0,
                "cmd_type": "object_list",
            }
        )

    assert server.command_queue.qsize() == ADMISSION_QUEUE_MAXSIZE

    res = server.handle_command(
        {
            "type": "create_cube",
            "op_id": "overflow-cmd",
            "params": {},
        }
    )

    assert res["status"] == "error"
    assert res["kind"] == "rate_limited"
    assert res["retryable"] is True
    assert "Admission queue full" in res["message"]


def test_client_handler_thread_cap_saturates_and_recovers():
    """H12: concurrent client handler threads are bounded by a semaphore.

    Once MAX_ACTIVE_CLIENT_THREADS slots are held, the next acquire fails
    (server must reject the client), and releasing a slot restores capacity.
    """
    server = BlenderMCPServer()
    assert MAX_ACTIVE_CLIENT_THREADS == 16

    for _ in range(MAX_ACTIVE_CLIENT_THREADS):
        assert server._client_slots.acquire(blocking=False) is True

    # Saturated: no slot for the next accepted client.
    assert server._client_slots.acquire(blocking=False) is False

    server._client_slots.release()
    assert server._client_slots.acquire(blocking=False) is True


def test_client_handler_slot_released_on_exception(monkeypatch):
    """H12: the concurrency slot is released in finally even on handler failure."""
    server = BlenderMCPServer()
    assert server._client_slots.acquire(blocking=False) is True

    def _boom(client):
        raise RuntimeError("handler exploded")

    monkeypatch.setattr(server, "_handle_client", _boom)

    class _FakeClient:
        pass

    with pytest.raises(RuntimeError):
        server._handle_client_slot(_FakeClient())

    # Slot was returned; capacity is fully restored.
    for _ in range(MAX_ACTIVE_CLIENT_THREADS):
        assert server._client_slots.acquire(blocking=False) is True


def test_commands_per_tick_budget(monkeypatch):
    server = BlenderMCPServer()
    server.running = True

    processed = []

    def mock_exec(cmd):
        processed.append(cmd["op_id"])
        return {"status": "success"}

    monkeypatch.setattr(server, "execute_command", mock_exec)

    for i in range(10):
        ev = threading.Event()
        server.command_queue.put_nowait(
            {
                "command": {"type": "object_list", "op_id": f"op-{i}"},
                "event": ev,
                "container": {"result": None},
                "op_id": f"op-{i}",
                "deadline": time.monotonic() + 10.0,
                "cmd_type": "object_list",
            }
        )

    server._process_queue()

    assert len(processed) == MAX_COMMANDS_PER_TICK
    assert server.command_queue.qsize() == 10 - MAX_COMMANDS_PER_TICK


def test_path_containment_allowed_and_rejected():
    with tempfile.TemporaryDirectory() as tmp_dir:
        safe_root = os.path.realpath(tmp_dir)
        inside_file = os.path.join(safe_root, "models", "cube.stl")
        outside_file = os.path.realpath(os.path.join(safe_root, "..", "outside.blend"))

        res = require_allowed(inside_file, [safe_root])
        assert res == os.path.abspath(inside_file)

        with pytest.raises(OutsideAllowRoots):
            require_allowed(outside_file, [safe_root])

        traversal = os.path.join(safe_root, "sub", "..", "..", "hacked.png")
        with pytest.raises(OutsideAllowRoots):
            require_allowed(traversal, [safe_root])


def test_path_containment_empty_roots_fail_closed():
    with pytest.raises(OutsideAllowRoots):
        require_allowed("some/path/file.fbx", [])
