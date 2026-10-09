"""Regression: lost Windows GUI stdio must not terminate Blender's native queue timer."""

import threading
import time
import traceback

from tests.test_bounded_queue_containment import BlenderMCPServer, server_mod


def test_native_queue_continues_when_stderr_traceback_fails(monkeypatch):
    server = BlenderMCPServer()
    server.running = True
    monkeypatch.setattr(server, "addon_log", lambda _message: None)
    monkeypatch.setattr(
        traceback,
        "print_exc",
        lambda: (_ for _ in ()).throw(OSError(22, "Invalid argument")),
    )

    def handler(cmd):
        if cmd["type"] == "create_torus":
            raise ValueError("intentional native operator failure")
        return {"status": "success", "message": "next request handled"}

    monkeypatch.setattr(server, "execute_command", handler)
    entries = []
    for name in ("create_torus", "document_info"):
        op_id = "stdio-" + name
        deadline = time.monotonic() + 8
        admitted, rejection = server.lifecycle.reserve_and_admit(name, op_id, {}, deadline)
        assert admitted and rejection is None
        event = threading.Event()
        result = {"result": None}
        server.command_queue.put_nowait(
            {
                "command": {"type": name, "op_id": op_id, "params": {}},
                "event": event,
                "container": result,
                "op_id": op_id,
                "deadline": deadline,
            }
        )
        entries.append((event, result))

    assert server._process_queue() is not None
    assert all(event.is_set() for event, _ in entries)
    assert entries[0][1]["result"]["status"] == "error"
    assert entries[1][1]["result"]["status"] == "success"


def test_native_execute_survives_broken_gui_stdout(monkeypatch):
    server = BlenderMCPServer()
    monkeypatch.setattr(
        server_mod,
        "print",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError(22, "Invalid argument")),
        raising=False,
    )
    monkeypatch.setattr(
        BlenderMCPServer,
        "__getattr__",
        lambda _self, _name: lambda **_kw: {"status": "success"},
        raising=False,
    )
    monkeypatch.setattr(
        server, "get_runtime_context", lambda: {"status": "success", "runtime_generation": "test"}
    )
    result = server.execute_command(
        {"type": "get_runtime_context", "params": {}, "request_id": "stdio-test"}
    )
    assert result["status"] == "success"
