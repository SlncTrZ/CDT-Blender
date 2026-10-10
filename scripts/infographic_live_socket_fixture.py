"""Isolated headless Blender L2 socket E2E harness, with deterministic teardown.

Runs addon socket on user-chosen loopback port (default 8891) without opening
or modifying any user scene. The main thread explicitly drains the real addon
command queue, matching the bpy.app.timer dispatch contract under -b mode.
Stop by writing a '.stop' file to the owned sandbox directory; auto expires.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from blender_mcp_addon.server import BlenderMCPServer


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sandbox", required=True, type=Path)
    parser.add_argument("--port", type=int, default=8891)
    parser.add_argument("--max-seconds", type=int, default=600)
    args = parser.parse_args(
        sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    )
    sandbox = args.sandbox.resolve(strict=True)
    if not sandbox.is_dir() or any(sandbox.iterdir()):
        raise ValueError("E2E sandbox must be an existing empty directory")
    if not 1024 <= args.port <= 65535 or not 30 <= args.max_seconds <= 1800:
        raise ValueError("Invalid port/time bound")
    if not bpy.app.background:
        raise RuntimeError("E2E socket fixture must run in isolated background Blender")

    s = BlenderMCPServer()
    started = s.start_server(host="127.0.0.1", port=args.port)
    if not started.get("ok") or started.get("already_running"):
        raise RuntimeError(f"Cannot start dedicated E2E socket: {started}")
    (sandbox / ".ready").write_text(
        json.dumps(
            {
                "blender": bpy.app.version_string,
                "port": args.port,
                "generation": s.runtime_generation,
                "scene_dirty": bpy.data.is_dirty,
            }
        ),
        encoding="utf-8",
    )
    print("BLENDER_E2E_READY:" + bpy.app.version_string, flush=True)
    deadline = time.monotonic() + args.max_seconds
    requests = 0
    try:
        while time.monotonic() < deadline:
            s._process_queue()
            requests += 1
            if (sandbox / ".stop").is_file():
                break
            time.sleep(0.014)
    finally:
        s.stop_server()
        (sandbox / ".finished").write_text(
            json.dumps(
                {
                    "polls": requests,
                    "blender": bpy.app.version_string,
                    "filepath": bpy.data.filepath,
                }
            ),
            encoding="utf-8",
        )
        print("BLENDER_E2E_STOPPED", flush=True)


if __name__ == "__main__":
    main()
