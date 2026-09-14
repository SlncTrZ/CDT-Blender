"""Bridge socket deadline tests.
Wing: blender | Topic: transport-reliability | Updated: 2026-09-14 16:50
"""

from __future__ import annotations

import time

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
