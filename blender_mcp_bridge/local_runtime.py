# blender_mcp_bridge/local_runtime.py
"""Local single-host runtime adapter — B1 seam over the existing addon socket.

Wing: code | Topic: migration-b1-seam | Updated: 2026-10-07 13:25

Wraps exactly one existing ``BlenderConnection`` (default: the shared
``blender`` singleton). Transport stays provider-local: the current TCP
connect/send/receive deadlines and byte budgets inside connection.py are
untouched — this class creates no transport of its own and never retries.

The addon socket remains workstation-local. This adapter never binds, listens,
or exposes the addon protocol on any interface; LAN exposure stays refused
(addon ``start_server`` fails closed on non-loopback binds).
"""

from __future__ import annotations

import socket
from typing import Any
from uuid import uuid4

from . import provider_contract as contract
from .config import settings
from .connection import BlenderConnection, blender
from .runtime_port import BlenderRuntimePort

LOCAL_GENERATION = "local"

_RUNTIME_CONTEXT_TIMEOUT_SECONDS = 2.0


def _addon_probe() -> dict[str, Any]:
    """Socket-only reachability probe. Sends nothing; never raises."""
    host = settings.addon_host
    port = settings.addon_port
    try:
        sock = socket.create_connection((host, port), timeout=2)
        sock.close()
        return {"connected": True, "host": host, "port": port}
    except OSError as exc:
        return {"connected": False, "host": host, "port": port, "reason": str(exc)}


def _support_status(snapshot: dict[str, Any]) -> str:
    version = snapshot.get("blender_version_tuple")
    version_tuple = tuple(version) if isinstance(version, (list, tuple)) else ()
    if (
        version_tuple == contract.VERIFIED_BLENDER_VERSION_TUPLE
        and snapshot.get("platform_system") == contract.VERIFIED_PLATFORM_SYSTEM
    ):
        return "verified_native_baseline"
    return "unverified_runtime"


class LocalBlenderRuntimeAdapter(BlenderRuntimePort):
    """Single-host adapter: 1:1 delegation over the current addon connection."""

    def __init__(self, connection: BlenderConnection | None = None) -> None:
        target = blender if connection is None else connection
        if not isinstance(target, BlenderConnection):
            raise TypeError("LocalBlenderRuntimeAdapter requires a BlenderConnection")
        self._connection = target

    @property
    def backend(self) -> BlenderConnection:
        return self._connection

    @property
    def generation(self) -> str:
        return LOCAL_GENERATION

    def execute(
        self,
        op: str,
        params: dict[str, Any] | None = None,
        *,
        rid: str = "unknown",
        timeout_seconds: float = 120.0,
        op_id: str | None = None,
    ) -> dict[str, Any]:
        return self._connection.send_command(
            op, params, rid, timeout_seconds=timeout_seconds, op_id=op_id
        )

    def capabilities(self) -> dict[str, Any]:
        return {
            "provider_name": contract.PROVIDER_ID,
            "provider_version": contract.PROVIDER_VERSION,
            "contract_version": contract.CONTRACT_VERSION,
            "common_contract_version": contract.COMMON_CONTRACT_VERSION,
            "runtime_support": contract.RUNTIME_SUPPORT,
            "capabilities": contract.CAPABILITIES,
            "error_kinds": list(contract.ERROR_KINDS),
        }

    def status(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "provider_name": contract.PROVIDER_ID,
            "provider_version": contract.PROVIDER_VERSION,
            "contract_version": contract.CONTRACT_VERSION,
            "transport": "local",
            "generation": LOCAL_GENERATION,
            "addon": _addon_probe(),
        }

    def runtime_status(self) -> dict[str, Any]:
        """Bounded live context; fail-closed dict when the addon cannot answer."""
        probe = _addon_probe()
        if not probe.get("connected"):
            return {
                "backend_available": False,
                "context_available": False,
                "reason": "addon_unreachable",
            }
        try:
            response = self.execute(
                "get_runtime_context",
                {},
                rid=f"RUNTIMESTATUS-{uuid4().hex}",
                timeout_seconds=_RUNTIME_CONTEXT_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            return {
                "backend_available": True,
                "context_available": False,
                "reason": f"runtime_context_error: {exc}",
            }
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
        snapshot["runtime_support_status"] = _support_status(snapshot)
        return snapshot

    def health(self) -> dict[str, Any]:
        probe = _addon_probe()
        return {
            "transport": "local",
            "reachable": bool(probe.get("connected")),
            "generation": LOCAL_GENERATION,
            "provider": contract.PROVIDER_ID,
            "provider_version": contract.PROVIDER_VERSION,
            "addon": probe,
        }
