# blender_mcp_bridge/tools/provider.py
#
# Fork of seehiong/blender-mcp-bridge (MIT, see ATTRIBUTION.md).
# SlncTrZ provider-shell adaptation by SlncTrZ / Truong Cong Dinh.
#
# Read-only first-class provider tools (help, system_status,
# system_capabilities). Answered locally from the runtime docs/TOOL_GUIDE.md —
# they never touch the Blender addon, so they work while Blender is offline.

from __future__ import annotations

import os
import socket
from typing import Any

from mcp import types

from .. import provider_contract as contract
from ..config import settings
from ..connection import blender


def get_provider_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="help",
            description=(
                "Read-only operating contract for the blender provider: versions, "
                "authentication, capabilities and the complete usage guide. "
                "Call first; no side effects."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="system_status",
            description=(
                "Read-only liveness report: provider versions, transport mode, guide "
                "availability and Blender addon reachability (socket probe only). "
                "No side effects."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="system_capabilities",
            description=(
                "Read-only machine-readable capability map with supported/unsupported "
                "modes and refusal reasons. Preflight before calling mutating tools. "
                "No side effects."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


def _authentication_description() -> str:
    return (
        "Network (Streamable HTTP /mcp): Authorization: Bearer <token> (primary) or "
        "X-API-Key: <token> (compatibility); single authorization layer; fail-closed "
        "401/403. Credential source: BLENDER_MCP_TOKEN env / secret manager. Never in "
        "URLs, tool args, logs, or Git-tracked config. Health endpoint GET /healthz "
        "is unauthenticated liveness only."
    )


def _capability_summary() -> list[str]:
    return [
        "Scene diagnostics: scene/object info, distances, viewport screenshots",
        "Collections: hierarchy, move/duplicate/visibility",
        "Modeling: primitives, curves, modifiers, transforms, selection, mesh operators",
        "Materials, lighting/world, cameras, keyframe animation",
        "Rendering: settings, frames, animation, view generation",
        "Sculpt assists (deterministic): smooth/inflate/grab/symmetrize/dyntopo",
        "Interchange: STL/3MF/OBJ plus FBX and glTF export (Unreal Engine 5 lane)",
        "Print preparation: manifold checks, voxel remesh, repairs",
        "Native undo/redo history",
        "No atomic transactions; no brush strokes/masks/face-sets/multires yet",
    ]


def _addon_probe() -> dict[str, Any]:
    host = settings.addon_host
    port = settings.addon_port
    try:
        sock = socket.create_connection((host, port), timeout=2)
        sock.close()
        return {"connected": True, "host": host, "port": port}
    except OSError as exc:
        return {"connected": False, "host": host, "port": port, "reason": str(exc)}


def _runtime_support_status(snapshot: dict[str, Any]) -> str:
    version = snapshot.get("blender_version_tuple")
    version_tuple = tuple(version) if isinstance(version, (list, tuple)) else ()
    if (
        version_tuple == contract.VERIFIED_BLENDER_VERSION_TUPLE
        and snapshot.get("platform_system") == contract.VERIFIED_PLATFORM_SYSTEM
    ):
        return "verified_native_baseline"
    return "unverified_runtime"


def _runtime_context_snapshot() -> dict[str, Any]:
    """Return bounded runtime context; fail closed when the addon cannot answer."""
    probe = _addon_probe()
    if not probe.get("connected"):
        return {
            "backend_available": False,
            "context_available": False,
            "reason": "addon_unreachable",
        }

    response = blender.send_command("get_runtime_context", {}, rid="SYSCTX", timeout_seconds=2.0)
    if (
        not isinstance(response, dict)
        or response.get("status") != "success"
        or not isinstance(response.get("result"), dict)
    ):
        return {
            "backend_available": True,
            "context_available": False,
            "reason": "runtime_context_unavailable",
        }

    snapshot = dict(response["result"])
    snapshot["backend_available"] = True
    snapshot["context_available"] = True
    snapshot["runtime_support_status"] = _runtime_support_status(snapshot)
    return snapshot


def handle_help(_args: dict[str, Any]) -> dict[str, Any]:
    content = contract.read_guide()
    guide_file = contract.guide_path()
    return {
        "provider_name": contract.PROVIDER_ID,
        "provider_version": contract.PROVIDER_VERSION,
        "protocol_version": contract.PROTOCOL_VERSION,
        "contract_version": contract.CONTRACT_VERSION,
        "common_contract_version": contract.COMMON_CONTRACT_VERSION,
        "contract_hash": contract.contract_hash(content),
        "updated_at": (os.path.getmtime(guide_file) if guide_file else None),
        "authentication": _authentication_description(),
        "capabilities": _capability_summary(),
        "content": content,
    }


def handle_system_status(_args: dict[str, Any]) -> dict[str, Any]:
    guide = contract.read_guide()
    return {
        "status": "ok",
        "provider_name": contract.PROVIDER_ID,
        "provider_version": contract.PROVIDER_VERSION,
        "contract_version": contract.CONTRACT_VERSION,
        "contract_hash": contract.contract_hash(guide),
        "transport": "http",
        "bridge": {"host": settings.bridge_host, "port": settings.bridge_port},
        "guide_available": len(guide) > 0,
        "addon": _addon_probe(),
    }


def handle_system_capabilities(_args: dict[str, Any]) -> dict[str, Any]:
    return {
        "provider_name": contract.PROVIDER_ID,
        "contract_version": contract.CONTRACT_VERSION,
        "common_contract_version": contract.COMMON_CONTRACT_VERSION,
        "backend_note": (
            "in-Blender addon over local TCP; UI-context capabilities require a "
            "running Blender with the addon started. Current UI/mode/object readiness is "
            "reported through runtime_context; no unverified context-specific error kind is claimed."
        ),
        "runtime_support": contract.RUNTIME_SUPPORT,
        "capabilities": contract.CAPABILITIES,
        "runtime_context": _runtime_context_snapshot(),
        "error_kinds": list(contract.ERROR_KINDS),
        "refusal_policy": (
            "Unsupported capabilities fail with kind unsupported_capability "
            "(retryable: false). No fake success, no silent fallback."
        ),
    }


PROVIDER_HANDLERS = {
    "help": handle_help,
    "system_status": handle_system_status,
    "system_capabilities": handle_system_capabilities,
}
