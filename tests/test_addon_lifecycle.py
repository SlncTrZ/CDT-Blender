"""Addon lifecycle tests.
Wing: blender | Topic: live-addon-lifecycle | Updated: 2026-09-14 19:45
"""

from __future__ import annotations

import importlib.util
import json
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
    setattr(modeling, "ModelingTools", type("ModelingTools", (), {}))  # noqa: B010
    monkeypatch.setitem(sys.modules, modeling.__name__, modeling)

    utils = types.ModuleType("blender_mcp_addon.utils")
    setattr(utils, "DEFAULT_HOST", "127.0.0.1")  # noqa: B010
    setattr(utils, "DEFAULT_PORT", 8888)  # noqa: B010
    monkeypatch.setitem(sys.modules, utils.__name__, utils)

    spec = importlib.util.spec_from_file_location("blender_mcp_addon.server", SERVER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module, timers


def _load_addon_module(monkeypatch):
    bpy = types.SimpleNamespace(
        types=types.SimpleNamespace(
            Operator=FakeOperator, Panel=FakePanel, AddonPreferences=object
        ),
        props=types.SimpleNamespace(BoolProperty=lambda **kw: kw, IntProperty=lambda **kw: kw),
        context=types.SimpleNamespace(preferences=types.SimpleNamespace(addons={})),
        utils=types.SimpleNamespace(
            register_class=lambda _cls: None, unregister_class=lambda _cls: None
        ),
    )
    monkeypatch.setitem(sys.modules, "bpy", bpy)

    server = types.ModuleType("blender_mcp_addon.server")
    setattr(server, "BlenderMCPServer", type("BlenderMCPServer", (), {}))  # noqa: B010
    monkeypatch.setitem(sys.modules, server.__name__, server)

    utils = types.ModuleType("blender_mcp_addon.utils")
    setattr(utils, "DEFAULT_PORT", 8888)  # noqa: B010
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

        def start_server(self, **kwargs):
            return {"ok": False, "state": "stopped", "error": self.last_error}

    setattr(module, "_server_instance", FailingServer())  # noqa: B010
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

    result = None
    for _ in range(repeat + 1):
        result = server.stop_server()

    assert result == {"ok": True, "state": "stopped"}
    assert server.running is False
    assert server.server_socket is None
    assert server.server_thread is None
    assert server.timer_handle is None


class ScriptedClient:
    def __init__(self, events):
        self.events = list(events)
        self.sent: list[bytes] = []
        self.timeouts: list[float] = []
        self.closed = False

    def settimeout(self, timeout):
        self.timeouts.append(timeout)

    def recv(self, _size):
        if not self.events:
            return b""
        event = self.events.pop(0)
        if isinstance(event, BaseException):
            raise event
        return event

    def sendall(self, data):
        self.sent.append(data)

    def close(self):
        self.closed = True


def _last_response(client: ScriptedClient):
    assert client.sent
    return json.loads(client.sent[-1].decode("utf-8"))


def test_addon_transport_reassembles_fragmented_json_request(monkeypatch):
    module, _timers = _load_server_module(monkeypatch)
    server = module.BlenderMCPServer()
    received = []

    def mock_handle_command(command):
        received.append(command)
        return {
            "status": "success",
            "result": {"ok": True},
        }

    server.handle_command = mock_handle_command
    client = ScriptedClient(
        [b'{"type":"get_runtime_', b'context","params":{},"request_id":"frag"}']
    )

    server._handle_client(client)

    assert received == [{"type": "get_runtime_context", "params": {}, "request_id": "frag"}]
    assert _last_response(client) == {"status": "success", "result": {"ok": True}}
    assert client.closed is True


def test_addon_transport_rejects_malformed_eof_with_typed_error(monkeypatch):
    module, _timers = _load_server_module(monkeypatch)
    server = module.BlenderMCPServer()
    client = ScriptedClient([b'{"type":', b""])

    server._handle_client(client)

    response = _last_response(client)
    assert response["status"] == "error"
    assert response["kind"] == "validation_error"
    assert response["retryable"] is False
    assert client.closed is True


def test_addon_transport_times_out_idle_sender_with_typed_error(monkeypatch):
    module, _timers = _load_server_module(monkeypatch)
    server = module.BlenderMCPServer()
    client = ScriptedClient([TimeoutError("idle")])

    server._handle_client(client)

    response = _last_response(client)
    assert response["status"] == "error"
    assert response["kind"] == "timeout"
    assert response["retryable"] is True
    assert client.closed is True


def test_addon_transport_rejects_request_over_budget(monkeypatch):
    module, _timers = _load_server_module(monkeypatch)
    monkeypatch.setattr(module, "MAX_REQUEST_BYTES", 32, raising=False)
    server = module.BlenderMCPServer()
    client = ScriptedClient([b'{"type":"x","params":{"blob":"' + b"a" * 64])

    server._handle_client(client)

    response = _last_response(client)
    assert response["status"] == "error"
    assert response["kind"] == "validation_error"
    assert "request" in response["message"].lower()
    assert "budget" in response["message"].lower()


def test_addon_transport_replaces_oversized_response_with_typed_error(monkeypatch):
    module, _timers = _load_server_module(monkeypatch)
    monkeypatch.setattr(module, "MAX_RESPONSE_BYTES", 64, raising=False)
    server = module.BlenderMCPServer()
    server.handle_command = lambda _command: {
        "status": "success",
        "result": {"blob": "x" * 256},
    }
    client = ScriptedClient([b'{"type":"get_runtime_context","params":{}}'])

    server._handle_client(client)

    response = _last_response(client)
    assert response["status"] == "error"
    assert response["kind"] == "internal_error"
    assert response["retryable"] is False
    assert "response" in response["message"].lower()
    assert "budget" in response["message"].lower()


def test_autostart_attaches_once_without_document_operations(monkeypatch):
    module = _load_addon_module(monkeypatch)
    calls = []
    prefs = types.SimpleNamespace(auto_start=True, port=8888)
    module.bpy.context.preferences.addons["blender_mcp_addon"] = types.SimpleNamespace(
        preferences=prefs
    )

    class Server:
        def start_server(self, **kwargs):
            calls.append(kwargs)
            return {"ok": True}

    module._server_instance = Server()
    assert module._auto_start() is None
    assert calls == [{"host": "127.0.0.1", "port": 8888}]
    prefs.auto_start = False
    module._auto_start()
    assert len(calls) == 1


def test_autostart_timer_survives_initial_document_load(monkeypatch):
    module = _load_addon_module(monkeypatch)
    calls = []
    module.bpy.app = types.SimpleNamespace(
        timers=types.SimpleNamespace(
            register=lambda function, **kwargs: calls.append((function, kwargs))
        )
    )
    module.register()
    assert calls == [(module._auto_start, {"first_interval": 1.0, "persistent": True})]
