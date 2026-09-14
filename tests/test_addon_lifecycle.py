"""Addon lifecycle tests.
Wing: blender | Topic: live-addon-lifecycle | Updated: 2026-09-14 19:45
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ADDON_INIT_PATH = ROOT / "blender_mcp_addon" / "__init__.py"
SERVER_PATH = ROOT / "blender_mcp_addon" / "server.py"


class FakeOperator:
    def __init__(self) -> None:
        self.reports: list[tuple[set[str], str]] = []

    def report(self, levels, message):
        self.reports.append((levels, message))


class FakePanel:
    pass


class FakeTimers:
    def __init__(self) -> None:
        self.registered: set[object] = set()
        self.register_calls: list[dict[str, object]] = []
        self.unregister_calls: list[object] = []

    def register(self, function, **kwargs):
        self.register_calls.append({"function": function, **kwargs})
        self.registered.add(function)

    def unregister(self, function):
        self.unregister_calls.append(function)
        self.registered.remove(function)

    def is_registered(self, function) -> bool:
        return function in self.registered


class FakeSocket:
    def __init__(self, *, bind_error: OSError | None = None) -> None:
        self.bind_error = bind_error
        self.closed = False
        self.timeout = None

    def setsockopt(self, *_args):
        return None

    def bind(self, _address):
        if self.bind_error is not None:
            raise self.bind_error

    def listen(self, _backlog):
        return None

    def close(self):
        self.closed = True

    def settimeout(self, timeout):
        self.timeout = timeout

    def accept(self):
        raise TimeoutError


class FakeThread:
    def __init__(self, *, target, daemon):
        self.target = target
        self.daemon = daemon
        self.started = False
        self.join_calls: list[float | None] = []

    def start(self):
        self.started = True

    def join(self, timeout=None):
        self.join_calls.append(timeout)

    def is_alive(self):
        return False


def _load_server_module(monkeypatch):
    timers = FakeTimers()
    bpy = types.SimpleNamespace(app=types.SimpleNamespace(timers=timers))
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
    modeling.ModelingTools = type("ModelingTools", (), {})
    monkeypatch.setitem(sys.modules, modeling.__name__, modeling)

    utils = types.ModuleType("blender_mcp_addon.utils")
    utils.DEFAULT_HOST = "127.0.0.1"
    utils.DEFAULT_PORT = 8888
    monkeypatch.setitem(sys.modules, utils.__name__, utils)

    spec = importlib.util.spec_from_file_location("blender_mcp_addon.server", SERVER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module, timers


def _load_addon_module(monkeypatch):
    bpy = types.SimpleNamespace(
        types=types.SimpleNamespace(Operator=FakeOperator, Panel=FakePanel),
        utils=types.SimpleNamespace(
            register_class=lambda _cls: None, unregister_class=lambda _cls: None
        ),
    )
    monkeypatch.setitem(sys.modules, "bpy", bpy)

    server = types.ModuleType("blender_mcp_addon.server")
    server.BlenderMCPServer = type("BlenderMCPServer", (), {})
    monkeypatch.setitem(sys.modules, server.__name__, server)

    utils = types.ModuleType("blender_mcp_addon.utils")
    utils.DEFAULT_PORT = 8888
    monkeypatch.setitem(sys.modules, utils.__name__, utils)

    spec = importlib.util.spec_from_file_location(
        "blender_mcp_addon",
        ADDON_INIT_PATH,
        submodule_search_locations=[str(ROOT / "blender_mcp_addon")],
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


def test_addon_metadata_requires_verified_blender_minimum(monkeypatch):
    module = _load_addon_module(monkeypatch)

    assert module.bl_info["blender"] == (4, 5, 3)


def test_start_operator_reports_bind_failure_truthfully(monkeypatch):
    module = _load_addon_module(monkeypatch)

    class FailingServer:
        running = False
        last_error = "Failed to start server: address already in use"

        def start_server(self):
            return {"ok": False, "state": "stopped", "error": self.last_error}

    module._server_instance = FailingServer()
    operator = module.BLENDERMCP_OT_StartServer()

    result = operator.execute(None)

    assert result == {"CANCELLED"}
    assert operator.reports == [({"ERROR"}, "Failed to start server: address already in use")]


def test_timer_is_persistent_and_registration_is_idempotent(monkeypatch):
    module, timers = _load_server_module(monkeypatch)
    server = module.BlenderMCPServer()

    server._register_timer()
    server._register_timer()

    assert len(timers.register_calls) == 1
    assert timers.register_calls[0]["function"] == server._process_queue
    assert timers.register_calls[0]["persistent"] is True


def test_start_failure_is_truthful_and_cleans_partial_state(monkeypatch):
    module, timers = _load_server_module(monkeypatch)
    sock = FakeSocket(bind_error=OSError("address already in use"))
    monkeypatch.setattr(module.socket, "socket", lambda *_args, **_kwargs: sock)

    server = module.BlenderMCPServer()
    result = server.start_server()

    assert result["ok"] is False
    assert result["state"] == "stopped"
    assert server.running is False
    assert server.server_socket is None
    assert server.server_thread is None
    assert server.timer_handle is None
    assert timers.registered == set()
    assert sock.closed is True


def test_start_stop_restart_has_single_timer_and_resets_resources(monkeypatch):
    module, timers = _load_server_module(monkeypatch)
    sockets: list[FakeSocket] = []
    threads: list[FakeThread] = []

    def make_socket(*_args, **_kwargs):
        sock = FakeSocket()
        sockets.append(sock)
        return sock

    def make_thread(*, target, daemon):
        thread = FakeThread(target=target, daemon=daemon)
        threads.append(thread)
        return thread

    monkeypatch.setattr(module.socket, "socket", make_socket)
    monkeypatch.setattr(module.threading, "Thread", make_thread)

    server = module.BlenderMCPServer()

    first = server.start_server()
    duplicate = server.start_server()
    server.stop_server()
    second = server.start_server()

    assert first == {"ok": True, "state": "running", "already_running": False}
    assert duplicate == {"ok": True, "state": "running", "already_running": True}
    assert second == {"ok": True, "state": "running", "already_running": False}
    assert len(sockets) == 2
    assert sockets[0].closed is True
    assert len(threads) == 2
    assert threads[0].join_calls
    assert len(timers.register_calls) == 2
    assert len(timers.unregister_calls) == 1
    assert timers.is_registered(server._process_queue)


@pytest.mark.parametrize("repeat", range(3))
def test_repeated_stop_is_idempotent(monkeypatch, repeat):
    module, _timers = _load_server_module(monkeypatch)
    server = module.BlenderMCPServer()

    for _ in range(repeat + 1):
        result = server.stop_server()

    assert result == {"ok": True, "state": "stopped"}
    assert server.running is False
    assert server.server_socket is None
    assert server.server_thread is None
    assert server.timer_handle is None
