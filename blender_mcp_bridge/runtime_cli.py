"""Private workstation agent entry point; credential output is for captured IPC only."""

from __future__ import annotations

import argparse
import json
import secrets
import signal
import sys
import threading

from .credential_pipe import CredentialBroker, read_credential
from .local_runtime import LocalBlenderRuntimeAdapter
from .workstation_agent import WorkstationAgentConfig, WorkstationBlenderRuntimeAgent


def serve_agent(pipe: str, port: int) -> None:
    token = secrets.token_urlsafe(48)
    agent = WorkstationBlenderRuntimeAgent(
        LocalBlenderRuntimeAdapter(),
        WorkstationAgentConfig(port=port, auth_token=token, require_native_generation=True),
    )
    broker = CredentialBroker(
        pipe, {"token": token, "generation": agent.generation, "port": str(port)}
    )
    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    try:
        broker.start()
        agent.start()
        print(json.dumps({"state": "ready", "generation": agent.generation}), file=sys.stderr)
        while broker.alive and not stop.wait(0.25):
            pass
    finally:
        agent.stop()
        broker.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Blender workstation runtime")
    parser.add_argument("command", choices=["serve", "credential"])
    parser.add_argument("--pipe", default="cdt-blender-runtime")
    parser.add_argument("--port", type=int, default=9868)
    args = parser.parse_args()
    try:
        if args.command == "serve":
            serve_agent(args.pipe, args.port)
        else:
            # Caller MUST capture this inherited stream in memory, never a terminal/log.
            sys.stdout.write(json.dumps(read_credential(args.pipe)))
            sys.stdout.flush()
    except Exception:
        # Suppress credential-bearing exception text at this process boundary.
        print("Blender runtime credential channel unavailable", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
