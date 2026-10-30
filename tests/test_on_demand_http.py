"""P0: gateway HTTP discovery survives an unattached Windows runtime.

Uses a disposable loopback port only; no native CAD/Blender session touched.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_offline_bridge_is_discoverable_and_authentication_stays_required(monkeypatch):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    env = dict(os.environ)
    env.update(
        {
            "BLENDER_RUNTIME_MODE": "remote",
            "BLENDER_RUNTIME_ON_DEMAND": "1",
            "BLENDER_RUNTIME_URL": "http://127.0.0.1:19868",
            "BLENDER_RUNTIME_PLATFORM": "Windows",
            "BLENDER_ASSETS_DIR": r"C:\CDT\assets",
            "BLENDER_ALLOW_ROOTS_JSON": json.dumps([r"C:\CDT\assets"]),
            "BLENDER_MCP_TOKEN": "test-only-gateway-placeholder",
        }
    )
    for key in (
        "BLENDER_RUNTIME_TOKEN_FD",
        "BLENDER_RUNTIME_GENERATION",
        "MCP_ALLOW_UNAUTHENTICATED",
    ):
        env.pop(key, None)
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "blender_mcp_bridge.main",
            "serve",
            "--transport",
            "http",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=ROOT,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        base = f"http://127.0.0.1:{port}"
        for _ in range(50):
            if proc.poll() is not None:
                pytest.fail("HTTP bridge exited before reaching standalone health readiness")
            try:
                with urllib.request.urlopen(base + "/healthz", timeout=1) as response:
                    assert response.status == 200
                    assert json.load(response)["provider"] == "blender"
                    break
            except (urllib.error.URLError, TimeoutError):
                time.sleep(0.1)
        else:
            pytest.fail("Bridge did not start during bounded standby check")

        message = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "standby-regression", "version": "1"},
                },
            }
        ).encode()
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        with pytest.raises(urllib.error.HTTPError) as denied:
            urllib.request.urlopen(
                urllib.request.Request(base + "/mcp/", message, headers),
                timeout=5,
            )
        assert denied.value.code == 401
        denied.value.close()

        authorized = dict(headers, Authorization="Bearer " + env["BLENDER_MCP_TOKEN"])
        with urllib.request.urlopen(
            urllib.request.Request(base + "/mcp/", message, authorized),
            timeout=5,
        ) as response:
            assert response.status == 200
            assert b"serverInfo" in response.read()

        tools_message = json.dumps(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        ).encode()
        with urllib.request.urlopen(
            urllib.request.Request(base + "/mcp/", tools_message, authorized),
            timeout=5,
        ) as response:
            assert response.status == 200
            body = response.read()
            assert b'"tools"' in body
            assert b"system_status" in body

        # Even when the catalog remains visible, an offline native read must
        # fail without attempting to reach a workstation or mutate a scene.
        offline_call = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "document_info", "arguments": {}},
            }
        ).encode()
        with urllib.request.urlopen(
            urllib.request.Request(base + "/mcp/", offline_call, authorized),
            timeout=5,
        ) as response:
            assert response.status == 200
            assert b"provider_unavailable" in response.read()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)
