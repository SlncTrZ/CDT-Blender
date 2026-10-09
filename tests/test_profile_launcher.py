"""Installed profile IPC and explicit binding boundaries."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
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
