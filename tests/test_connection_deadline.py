"""Bridge socket deadline tests.
Wing: blender | Topic: transport-reliability | Updated: 2026-09-14 16:50
"""

from __future__ import annotations

import time

from blender_mcp_bridge import connection
from blender_mcp_bridge.connection import BlenderConnection


class AlwaysTimeoutSocket:
    def __init__(self):
        self.calls = 0

    def settimeout(self, _timeout):
        pass

    def recv(self, _size):
        self.calls += 1
        raise TimeoutError("no data")


def test_recv_all_stops_at_total_deadline():
    conn = BlenderConnection()
    sock = AlwaysTimeoutSocket()
    started = time.monotonic()

    data = conn.recv_all(sock, deadline=started + 0.02)

    elapsed = time.monotonic() - started
    assert data == b""
    assert sock.calls > 0
    assert elapsed < 0.5


class ChunkSocket:
    def __init__(self, chunks):
        self.chunks = list(chunks)

    def settimeout(self, _timeout):
        pass

    def recv(self, _size):
        return self.chunks.pop(0) if self.chunks else b""


def test_recv_all_rejects_response_over_budget():
    conn = BlenderConnection()
    sock = ChunkSocket([b"1234", b"5678"])

    try:
        conn.recv_all(sock, deadline=time.monotonic() + 1.0, max_bytes=6)
    except ValueError as exc:
        assert "response" in str(exc).lower()
        assert "budget" in str(exc).lower()
    else:
        raise AssertionError("oversized response must fail")


def test_send_command_rejects_request_over_budget_before_connect(monkeypatch):
    monkeypatch.setattr(connection, "MAX_REQUEST_BYTES", 64, raising=False)
    monkeypatch.setattr(
        connection.socket,
        "socket",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("oversized request must fail before socket creation")
        ),
    )

    result = BlenderConnection().send_command("create_text", {"text": "x" * 256})

    assert result["status"] == "error"
    assert result["kind"] == "validation_error"
    assert result["retryable"] is False
    assert "request" in result["message"].lower()
    assert "budget" in result["message"].lower()


class ConnectTimeoutSocket:
    def __init__(self):
        self.timeouts: list[float] = []
        self.closed = False

    def settimeout(self, timeout):
        self.timeouts.append(timeout)

    def connect(self, _address):
        raise TimeoutError("connect timeout")

    def close(self):
        self.closed = True


def test_send_command_connect_uses_remaining_total_deadline(monkeypatch):
    sock = ConnectTimeoutSocket()
    ticks = iter([100.0, 100.25])
    monkeypatch.setattr(connection.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(connection.socket, "socket", lambda *_args, **_kwargs: sock)

    result = BlenderConnection().send_command("get_runtime_context", timeout_seconds=1.0)

    assert 0.0 < sock.timeouts[0] <= 0.75
    assert result["status"] == "error"
    assert result["kind"] == "provider_unavailable"
    assert result["retryable"] is True
    assert sock.closed is True
