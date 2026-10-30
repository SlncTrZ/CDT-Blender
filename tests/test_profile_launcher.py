"""Installed profile IPC and explicit binding boundaries."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def launcher():
    spec = importlib.util.spec_from_file_location(
        "profile_launcher", ROOT / "scripts" / "launch_runtime_profile.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def config():
    return {
        "workstation_python": r"C:\CDT\venv\Scripts\python.exe",
        "credential_pipe": "cdt-blender-test",
        "ssh_target": "fixture@127.0.0.1",
        "agent_port": 9868,
        "provider_python": "/fixture/python",
        "runtime_url": "http://127.0.0.1:19868",
        "runtime_platform": "Windows",
        "assets_dir": r"C:\CDT\assets",
        "allow_roots": [r"C:\CDT\assets"],
    }


def test_profile_operator_cli_is_packaged_from_exact_script():
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert (
        metadata["project"]["scripts"]["cdt-blender-profile"]
        == "blender_mcp_bridge.profile_launcher:main"
    )
    force_include = metadata["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"]
    assert (
        force_include["scripts/launch_runtime_profile.py"]
        == "blender_mcp_bridge/profile_launcher.py"
    )
    assert (ROOT / "scripts/launch_runtime_profile.py").is_file()


def test_ssh_credential_lookup_cannot_consume_mcp_stdin(monkeypatch, capsys):
    module = launcher()
    seen = []
    payload = {"token": "fixture-secret", "generation": "gen-fixture", "port": "9868"}

    def execute(argv, **kwargs):
        seen.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, json.dumps(payload).encode(), b"")

    monkeypatch.setattr(module.subprocess, "run", execute)
    assert module.credential(config()) == payload
    argv, kwargs = seen[0]
    assert kwargs["stdin"] is subprocess.DEVNULL
    assert kwargs["capture_output"] is True and kwargs["timeout"] <= 15
    assert "StrictHostKeyChecking=yes" in argv and "BatchMode=yes" in argv
    assert "fixture-secret" not in repr(argv)
    assert not capsys.readouterr().out


def test_launch_passes_credential_only_through_inherited_descriptor(monkeypatch):
    module = launcher()
    monkeypatch.setenv("PYTHONPATH", "/unrelated-source")
    seen = []

    def execute(path, argv, env):
        fd = int(env["BLENDER_RUNTIME_TOKEN_FD"])
        seen.append(fd)
        assert os.read(fd, 4096) == b"fixture-secret"
        assert "PYTHONPATH" not in env
        assert "fixture-secret" not in repr(argv) + repr(env)
        assert env["BLENDER_RUNTIME_GENERATION"] == "gen-old"
        assert argv[-2:] == ["--transport", "stdio"]
        raise RuntimeError("fixture exec boundary")

    monkeypatch.setattr(module.os, "execve", execute)
    with pytest.raises(RuntimeError):
        module.launch(config(), {"token": "fixture-secret"}, {"generation": "gen-old"})
    with pytest.raises(OSError):
        os.fstat(seen[0])


def test_bind_requires_exact_operator_accepted_generation(monkeypatch, tmp_path, capsys):
    module = launcher()
    binding = tmp_path / "binding.json"
    binding.write_text('{"generation":"gen-old"}')
    profile = tmp_path / "profile.json"
    profile.write_text(json.dumps({"binding_file": str(binding)}))
    monkeypatch.setattr(module, "verify_install", lambda _: None)
    monkeypatch.setattr(
        module,
        "credential",
        lambda _: {"token": "fixture-secret", "generation": "gen-new", "port": "9868"},
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["launch", "bind", "--profile", str(profile), "--accept-generation", "gen-old"],
    )
    with pytest.raises(SystemExit) as exit_info:
        module.main()
    assert exit_info.value.code == 1
    assert json.loads(binding.read_text()) == {"generation": "gen-old"}
    output = capsys.readouterr()
    assert not output.out and "fixture-secret" not in output.err


def test_binding_refuses_legacy_release_path_before_ssh(monkeypatch, tmp_path):
    module = launcher()
    release = tmp_path / "v0.2.1"
    legacy = tmp_path / "legacy"
    release.mkdir()
    legacy.mkdir()
    profile = release / "profile.json"
    profile.write_text(json.dumps({"binding_file": str(legacy / "binding.json")}))
    (legacy / "binding.json").write_text('{"generation":"gen-old"}')
    (release / "binding.json").write_text('{"generation":"gen-current"}')
    monkeypatch.setattr(module, "verify_install", lambda _: None)
    monkeypatch.setattr(module, "credential", lambda _: pytest.fail("must not call SSH"))
    monkeypatch.setattr(
        sys,
        "argv",
        ["launch", "bind", "--profile", str(profile), "--accept-generation", "gen-current"],
    )
    with pytest.raises(SystemExit) as exc:
        module.main()
    assert exc.value.code == 1
    assert json.loads((legacy / "binding.json").read_text())["generation"] == "gen-old"
    assert json.loads((release / "binding.json").read_text())["generation"] == "gen-current"


def test_standby_http_launch_does_not_need_workstation_credential(monkeypatch, tmp_path):
    module = launcher()
    profile = tmp_path / "profile.json"
    profile.write_text(json.dumps({"binding_file": str(tmp_path / "binding.json")}))
    monkeypatch.setenv("BLENDER_MCP_TOKEN", "gateway-only-fixture")
    monkeypatch.setenv("MCP_ALLOW_UNAUTHENTICATED", "1")
    monkeypatch.setenv("PYTHONPATH", "/unrelated")
    monkeypatch.setattr(module, "credential", lambda _: pytest.fail("must not call agent"))
    executed = []

    def execute(path, argv, env):
        executed.append((path, argv, env))
        raise RuntimeError("exec intercepted")

    monkeypatch.setattr(module.os, "execve", execute)
    with pytest.raises(RuntimeError, match="exec intercepted"):
        module.serve_http(
            config() | {"binding_file": str(tmp_path / "binding.json")}, profile, port=8812
        )
    assert len(executed) == 1
    _, argv, env = executed[0]
    assert argv[-4:] == ["--host", "127.0.0.1", "--port", "8812"]
    assert env["BLENDER_MCP_TOKEN"] == "gateway-only-fixture"
    assert env["BLENDER_RUNTIME_ON_DEMAND"] == "1"
    assert "BLENDER_RUNTIME_GENERATION" not in env
    assert "BLENDER_RUNTIME_TOKEN_FD" not in env
    assert "MCP_ALLOW_UNAUTHENTICATED" not in env
    assert "PYTHONPATH" not in env


def test_standby_http_refuses_missing_independent_gateway_auth(monkeypatch, tmp_path):
    module = launcher()
    monkeypatch.delenv("BLENDER_MCP_TOKEN", raising=False)
    with pytest.raises(ValueError, match="independent managed Gateway"):
        module.launch_http(config(), None, None, port=8812)


def test_http_attach_only_matching_generation_and_preserves_separate_auth(monkeypatch):
    module = launcher()
    monkeypatch.setenv("BLENDER_MCP_TOKEN", "gateway-only-fixture")
    seen = []

    def execute(path, argv, env):
        descriptor = int(env["BLENDER_RUNTIME_TOKEN_FD"])
        assert os.read(descriptor, 4096) == b"runtime-only-fixture"
        seen.append((path, argv, env))
        raise RuntimeError("exec intercepted")

    monkeypatch.setattr(module.os, "execve", execute)
    with pytest.raises(RuntimeError, match="exec intercepted"):
        module.launch_http(
            config(),
            {"token": "runtime-only-fixture", "generation": "gen-current"},
            {"generation": "gen-current"},
            port=8812,
        )
    assert seen[0][2]["BLENDER_MCP_TOKEN"] == "gateway-only-fixture"
    assert seen[0][2]["BLENDER_RUNTIME_GENERATION"] == "gen-current"
    assert "runtime-only-fixture" not in repr(seen[0][2])
    with pytest.raises(ValueError, match="explicit operator generation binding"):
        module.launch_http(
            config(),
            {"token": "runtime-only-fixture", "generation": "gen-new"},
            {"generation": "gen-old"},
            port=8812,
        )


def test_http_workstation_credential_timeout_remains_standby(monkeypatch, tmp_path):
    module = launcher()
    profile = tmp_path / "profile.json"
    binding = tmp_path / "binding.json"
    binding.write_text('{"generation":"gen-old"}')
    config_data = config() | {"binding_file": str(binding)}
    monkeypatch.setenv("BLENDER_MCP_TOKEN", "gateway-only-fixture")

    def timed_out(_):
        raise subprocess.TimeoutExpired(["ssh", "fixture"], timeout=15)

    monkeypatch.setattr(module, "credential", timed_out)
    attempts = []
    monkeypatch.setattr(
        module,
        "launch_http",
        lambda cfg, value, stored, *, port: attempts.append((value, stored, port)),
    )
    module.serve_http(config_data, profile, port=8812)
    assert attempts == [(None, None, 8812)]


def test_http_refuses_shared_gateway_and_runtime_identity(monkeypatch):
    module = launcher()
    monkeypatch.setenv("BLENDER_MCP_TOKEN", "shared-fixture")
    with pytest.raises(ValueError, match="credentials must remain independent"):
        module.launch_http(
            config(),
            {"token": "shared-fixture", "generation": "gen-current"},
            {"generation": "gen-current"},
            port=8812,
        )


def test_http_offline_credential_and_stale_generation_do_not_crash(monkeypatch, tmp_path):
    module = launcher()
    profile = tmp_path / "profile.json"
    binding = tmp_path / "binding.json"
    binding.write_text('{"generation":"gen-old"}')
    monkeypatch.setenv("BLENDER_MCP_TOKEN", "gateway-only-fixture")
    monkeypatch.setattr(
        module, "credential", lambda _: {"token": "fixture", "generation": "gen-new"}
    )
    seen = []
    monkeypatch.setattr(
        module,
        "launch_http",
        lambda cfg, value, stored, *, port: seen.append((value, stored, port)),
    )
    module.serve_http(config() | {"binding_file": str(binding)}, profile, port=8812)
    assert seen == [(None, None, 8812)]
