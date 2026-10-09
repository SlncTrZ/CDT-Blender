"""Loss after a native effect requires reconciliation, never a clean retry."""

from __future__ import annotations

import json
import socket
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from blender_mcp_bridge import connection
from blender_mcp_bridge.connection import BlenderConnection
from blender_mcp_bridge.runtime_transport import (
    RemoteBlenderRuntimeTransport,
    RuntimeUncertainError,
)


@contextmanager
def native_peer(reply):
    effects = []
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    listener.settimeout(3)

    def serve():
        with listener.accept()[0] as client:
            payload = json.loads(client.recv(65536))
            effects.append(payload)
            if reply:
                client.sendall(reply)

    worker = threading.Thread(target=serve, daemon=True)
    worker.start()
    try:
        yield listener.getsockname()[1], effects
    finally:
        worker.join(3)
        listener.close()
        assert not worker.is_alive()


@pytest.mark.parametrize("reply", [b"", b"{broken", b"\xff", b"null", b"[]"])
def test_native_effect_with_untrusted_response_requires_reconciliation(monkeypatch, reply):
    with native_peer(reply) as (port, effects):
        monkeypatch.setattr(connection.settings, "addon_port", port)
        monkeypatch.setattr(connection.settings, "addon_host", "127.0.0.1")
        result = BlenderConnection().send_command(
            "create_cube", {"name": "owned"}, rid="receipt", op_id="stable-op", timeout_seconds=1
        )
        assert len(effects) == 1
        assert effects[0]["op_id"] == "stable-op"
        assert result["status"] == "error"
        assert result["kind"] == "timeout_uncertain"
        assert result["op_id"] == "stable-op"
        assert "reconcile" in result["message"].lower()


@contextmanager
def agent_peer(reply):
    effects = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            effects.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            self.send_response(200)
            self.send_header("Content-Length", str(len(reply)))
            self.end_headers()
            self.wfile.write(reply)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", effects
    finally:
        server.shutdown()
        server.server_close()
        worker.join(3)


def envelope(**changes):
    body = {
        "ok": True,
        "result": {"status": "success"},
        "error_code": "ok",
        "error_message": "",
        "generation": "gen-owned",
        "completion_unknown": False,
    }
    body.update(changes)
    return json.dumps(body).encode()


@pytest.mark.parametrize(
    "reply",
    [
        b"{broken",
        b"\xff",
        b"null",
        envelope(ok="false"),
        envelope(completion_unknown="false"),
        envelope(completion_unknown=True),
        envelope(error_code="backend_error"),
        envelope(generation="gen-other"),
        envelope(generation="unbound"),
        envelope(result=None),
        envelope(ok=False, result=None, error_code="backend_error"),
        envelope(ok=False, result=None, error_code="unexpected_code"),
    ],
)
def test_agent_effect_with_untrusted_response_is_uncertain_without_replay(reply):
    with agent_peer(reply) as (url, effects):
        transport = RemoteBlenderRuntimeTransport(url, "fixture-only")
        with pytest.raises(RuntimeUncertainError):
            transport.call("create_cube", op_id="stable-op", expected_generation="gen-owned")
        assert len(effects) == 1
        assert effects[0]["op_id"] == "stable-op"
