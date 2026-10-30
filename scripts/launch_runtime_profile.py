"""Launch an installed Blender provider using a captured workstation credential.

The profile JSON contains deployment coordinates and pinned source hashes only.
Credential values remain in memory and an inherited descriptor. This script is
an operator entry point, not a public MCP tool.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path


def credential(config: dict) -> dict:
    # Fixed administrator profile values; never accept arbitrary public tool inputs.
    executable = config["workstation_python"]
    pipe = config["credential_pipe"]
    if "'" in executable or "'" in pipe:
        raise ValueError("invalid workstation profile")
    command = f"& '{executable}' -m blender_mcp_bridge.runtime_cli credential --pipe '{pipe}'; exit $LASTEXITCODE"
    encoded = base64.b64encode(command.encode("utf-16le")).decode("ascii")
    completed = subprocess.run(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            "ConnectTimeout=5",
            config["ssh_target"],
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-EncodedCommand",
            encoded,
        ],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=15,
    )
    if completed.returncode:
        raise RuntimeError("workstation credential channel unavailable")
    value = json.loads(completed.stdout)
    if not isinstance(value, dict) or not all(
        isinstance(value.get(key), str) and value[key] for key in ("token", "generation", "port")
    ):
        raise ValueError("invalid credential envelope")
    if value["port"] != str(config["agent_port"]):
        raise ValueError("workstation credential belongs to another runtime endpoint")
    return value


def verify_install(config: dict) -> None:
    for name, expected in config["installed_hashes"].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest() != expected:
            raise ValueError("installed provider source hash mismatch")

def canonical_binding_file(profile_path: Path, config: dict) -> Path:
    """Refuse cross-release binding targets before any credential lookup or write."""
    expected = profile_path.resolve().parent / "binding.json"
    configured = Path(config["binding_file"]).resolve()
    if configured != expected:
        raise ValueError("profile binding file must belong to the installed release")
    return expected


def authenticated_heartbeat(config: dict, value: dict) -> bool:
    """Attest that a credential actually belongs to the current runtime."""
    if value["port"] != str(config["agent_port"]):
        return False
    request = urllib.request.Request(
        config["runtime_url"] + "/health",
        headers={"Authorization": "Bearer " + value["token"]},
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=5) as response:
        heartbeat = json.load(response)
    return heartbeat.get("ok") is True and heartbeat.get("generation") == value["generation"]


def launch_http(
    config: dict, value: dict | None, binding: dict | None, *, port: int
) -> None:
    """Run discoverable HTTP control plane; native access stays explicitly fenced."""
    env = dict(os.environ)
    if not env.get("BLENDER_MCP_TOKEN", "").strip():
        raise ValueError("independent managed Gateway MCP credential required")
    env.pop("MCP_ALLOW_UNAUTHENTICATED", None)
    env.pop("PYTHONPATH", None)
    env.pop("BLENDER_RUNTIME_TOKEN_FD", None)
    env.pop("BLENDER_RUNTIME_GENERATION", None)
    env.update(
        {
            "PYTHONNOUSERSITE": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "BLENDER_RUNTIME_MODE": "remote",
            "BLENDER_RUNTIME_ON_DEMAND": "1",
            "BLENDER_RUNTIME_URL": config["runtime_url"],
            "BLENDER_RUNTIME_PLATFORM": config["runtime_platform"],
            "BLENDER_ASSETS_DIR": config["assets_dir"],
            "BLENDER_ALLOW_ROOTS_JSON": json.dumps(config["allow_roots"]),
        }
    )
    reader = None
    if value is not None and binding is not None:
        if env["BLENDER_MCP_TOKEN"] == value["token"]:
            raise ValueError("Gateway and workstation credentials must remain independent")
        if value["generation"] != binding.get("generation"):
            raise ValueError("explicit operator generation binding required")
        reader, writer = os.pipe()
        try:
            os.write(writer, value["token"].encode("utf-8"))
        finally:
            os.close(writer)
        os.set_inheritable(reader, True)
        env["BLENDER_RUNTIME_TOKEN_FD"] = str(reader)
        env["BLENDER_RUNTIME_GENERATION"] = binding["generation"]
    try:
        os.execve(
            config["provider_python"],
            [
                config["provider_python"],
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
            env,
        )
    finally:
        if reader is not None:
            os.close(reader)


def serve_http(config: dict, profile_path: Path, *, port: int) -> None:
    """Never require the on-demand workstation to be online for discovery."""
    # A stale profile, offline broker or different runtime generation results in
    # standby, not an implicit rebind or an infinite service restart loop.
    value: dict | None = None
    binding: dict | None = None
    try:
        target = canonical_binding_file(profile_path, config)
        candidate = json.loads(target.read_text())
        if not isinstance(candidate.get("generation"), str) or not candidate["generation"]:
            raise ValueError("invalid release-local generation binding")
        current = credential(config)
        if (
            current["generation"] == candidate["generation"]
            and current["token"] != os.environ.get("BLENDER_MCP_TOKEN")
            and authenticated_heartbeat(config, current)
        ):
            value, binding = current, candidate
    except (KeyError, TypeError, ValueError, RuntimeError, OSError, subprocess.TimeoutExpired):
        # Remote timeout is a detached runtime, not a reason to crash-loop
        # the persistent, independently authenticated MCP control plane.
        pass
    launch_http(config, value, binding, port=port)


def launch(config: dict, value: dict, binding: dict) -> None:
    reader, writer = os.pipe()
    try:
        os.write(writer, value["token"].encode("utf-8"))
    finally:
        os.close(writer)
    os.set_inheritable(reader, True)
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("BLENDER_MCP_TOKEN", None)
    env.pop("MCP_ALLOW_UNAUTHENTICATED", None)
    env.update(
        {
            "PYTHONNOUSERSITE": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "BLENDER_RUNTIME_MODE": "remote",
            "BLENDER_RUNTIME_URL": config["runtime_url"],
            "BLENDER_RUNTIME_PLATFORM": config["runtime_platform"],
            "BLENDER_RUNTIME_GENERATION": binding["generation"],
            "BLENDER_RUNTIME_TOKEN_FD": str(reader),
            "BLENDER_ASSETS_DIR": config["assets_dir"],
            "BLENDER_ALLOW_ROOTS_JSON": json.dumps(config["allow_roots"]),
        }
    )
    try:
        os.execve(
            config["provider_python"],
            [
                config["provider_python"],
                "-m",
                "blender_mcp_bridge.main",
                "serve",
                "--transport",
                "stdio",
            ],
            env,
        )
    finally:
        os.close(reader)


def main() -> None:
    parser = argparse.ArgumentParser(description="Installed Blender runtime profile")
    parser.add_argument("command", choices=["serve", "bind", "serve-http"])
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--accept-generation")
    parser.add_argument("--port", type=int, default=8812)
    args = parser.parse_args()
    try:
        config = json.loads(args.profile.read_text())
        verify_install(config)
        if args.command == "serve-http":
            serve_http(config, args.profile, port=args.port)
            return
        binding_file = canonical_binding_file(args.profile, config)
        value = credential(config)
        if args.command == "bind":
            if not args.accept_generation or args.accept_generation != value["generation"]:
                raise ValueError("explicit current generation acceptance required")
            # Authenticate current agent identity before accepting a new generation.
            if not authenticated_heartbeat(config, value):
                raise ValueError("runtime heartbeat does not match accepted generation")
            temporary = binding_file.with_suffix(".tmp")
            with temporary.open("w") as stream:
                json.dump({"generation": args.accept_generation}, stream)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(binding_file)
            print(json.dumps({"bound": args.accept_generation}))
            return
        binding = json.loads(binding_file.read_text())
        if not isinstance(binding.get("generation"), str) or not binding["generation"]:
            raise ValueError("runtime profile has no explicit generation binding")
        # A changed agent generation is not rebound automatically. Provider identity
        # remains available; native dispatch refuses the stale generation before effects.
        launch(config, value, binding)
    except Exception:
        print(
            "Blender runtime profile unavailable; check install, tunnel and binding",
            file=sys.stderr,
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
