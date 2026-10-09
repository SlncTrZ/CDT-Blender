"""B5 runtime selection, fresh native context, and remote path boundaries."""

from __future__ import annotations

import json
import ntpath
import os
import subprocess
import sys

import pytest

from blender_mcp_bridge.remote_runtime import RemoteBlenderRuntimeAdapter
from blender_mcp_bridge.runtime_transport import BlenderRuntimeTransport


class CachedContextTransport(BlenderRuntimeTransport):
    def __init__(self):
        self.cache = {}
        self.mode = "OBJECT"
        self.native_available = True
        self.calls = []

    def call(self, op, params=None, **kwargs):
        self.calls.append((op, params, kwargs))
        if not self.native_available:
            return {"status": "error", "kind": "provider_unavailable", "message": "addon down"}
        rid = kwargs["rid"]
        return self.cache.setdefault(
            rid, {"status": "success", "result": {"active_mode": self.mode}}
        )

    def health(self):
        return {"generation": "gen-fixture", "adapter": {"reachable": self.native_available}}

    def close(self):
        pass


def test_remote_context_is_live_across_mode_changes():
    transport = CachedContextTransport()
    adapter = RemoteBlenderRuntimeAdapter(transport, expected_generation="gen-fixture")
    assert adapter.runtime_status()["active_mode"] == "OBJECT"
    transport.mode = "SCULPT"
    assert adapter.runtime_status()["active_mode"] == "SCULPT"
    assert len(transport.calls) == 2


def test_live_agent_does_not_claim_closed_blender_is_connected():
    transport = CachedContextTransport()
    transport.native_available = False
    adapter = RemoteBlenderRuntimeAdapter(transport, expected_generation="gen-fixture")
    assert adapter.status()["addon"]["connected"] is False
    assert adapter.runtime_status()["backend_available"] is False


def test_restart_health_requires_explicit_generation_binding():
    transport = CachedContextTransport()
    adapter = RemoteBlenderRuntimeAdapter(transport, expected_generation="gen-old")
    status = adapter.status()
    assert status["binding_ready"] is False
    assert status["addon"]["connected"] is False
    assert transport.calls == []


def windows_policy():
    from blender_mcp_bridge.path_policy import RuntimePathPolicy

    return RuntimePathPolicy("Windows", r"C:\CDT\assets", [r"C:\CDT\assets"])


@pytest.mark.parametrize(
    "value",
    [
        r"C:\CDT\assets\model.blend",
        r"c:/cdt/assets/model.blend",
        "model.blend",
    ],
)
def test_windows_paths_resolve_on_linux_without_local_filesystem(value):
    assert ntpath.normcase(windows_policy().resolve(value)) == r"c:\cdt\assets\model.blend"


@pytest.mark.parametrize(
    "value",
    [
        r"C:\CDT\assets-old\model.blend",
        r"..\model.blend",
        r"C:model.blend",
        r"\CDT\assets\model.blend",
        r"\\host\share\model.blend",
        r"\\?\C:\CDT\assets\model.blend",
        r"\\.\C:\CDT\assets\model.blend",
        r"C:\CDT\assets\model.blend:stream",
        "model.blend\x00",
    ],
)
def test_windows_paths_refuse_ambiguous_or_outside_paths(value):
    with pytest.raises(ValueError):
        windows_policy().resolve(value)


def test_runtime_factory_remote_requires_binding_and_shared_transport(monkeypatch):
    from blender_mcp_bridge.config import Config
    from blender_mcp_bridge.runtime_factory import create_runtime

    monkeypatch.setenv("BLENDER_RUNTIME_MODE", "remote")
    monkeypatch.setenv("BLENDER_RUNTIME_URL", "http://127.0.0.1:19868")
    monkeypatch.setenv("BLENDER_RUNTIME_PLATFORM", "Windows")
    monkeypatch.setenv("BLENDER_ASSETS_DIR", r"C:\CDT\assets")
    monkeypatch.setenv("BLENDER_ALLOW_ROOTS_JSON", json.dumps([r"C:\CDT\assets"]))
    config = Config()
    with pytest.raises(ValueError, match="generation"):
        create_runtime(config)
    monkeypatch.setenv("BLENDER_RUNTIME_GENERATION", "gen-fixture")
    fd, writer = os.pipe()
    os.write(writer, b"test-fixture-token")
    os.close(writer)
    monkeypatch.setenv("BLENDER_RUNTIME_TOKEN_FD", str(fd))
    bundle = create_runtime(Config())
    assert bundle.port._transport is bundle.transport
    assert bundle.port.generation == "gen-fixture"
    assert bundle.paths.resolve("model.blend") == r"C:\CDT\assets\model.blend"
    with pytest.raises(OSError):
        os.fstat(fd)


def test_stdio_initialize_has_no_banner_and_needs_no_http_token(tmp_path):
    message = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "qualification", "version": "1"},
        },
    }
    env = dict(os.environ, BLENDER_RUNTIME_MODE="local")
    env.pop("BLENDER_MCP_TOKEN", None)
    env.pop("MCP_ALLOW_UNAUTHENTICATED", None)
    completed = subprocess.run(
        [sys.executable, "-m", "blender_mcp_bridge.main", "serve", "--transport", "stdio"],
        input=json.dumps(message) + "\n",
        text=True,
        capture_output=True,
        timeout=15,
        env=env,
    )
    assert completed.returncode == 0, completed.stderr
    lines = [json.loads(line) for line in completed.stdout.splitlines()]
    assert len(lines) == 1 and lines[0]["id"] == 1
    assert lines[0]["result"]["serverInfo"]["name"] == "blender-mcp-bridge"


def test_agent_configuration_repr_does_not_expose_credential():
    from blender_mcp_bridge.workstation_agent import WorkstationAgentConfig

    assert "fixture-secret" not in repr(WorkstationAgentConfig(auth_token="fixture-secret"))


def test_credential_broker_repr_does_not_expose_payload():
    from blender_mcp_bridge.credential_pipe import CredentialBroker

    assert "fixture-secret" not in repr(
        CredentialBroker(
            "cdt-blender-test", {"token": "fixture-secret", "generation": "gen-fixture"}
        )
    )
