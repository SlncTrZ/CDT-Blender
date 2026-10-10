"""Windowless Windows task entry point for the CDT Blender workstation agent.

Use with pythonw.exe, NEVER a scheduled powershell.exe console. This script is
operator-only and does not alter tokens/credentials or expose bearer material.
Task Scheduler owns process lifetime; the runtime_cli mints its own token.
"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    sys.argv = ["blender_mcp_bridge.runtime_cli", "serve", *sys.argv[1:]]
    runpy.run_module("blender_mcp_bridge.runtime_cli", run_name="__main__")


if __name__ == "__main__":
    main()
