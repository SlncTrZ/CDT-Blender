# blender_mcp_bridge/runtime_port.py
"""Blender runtime port — provider/execution seam for migration B1.

Wing: code | Topic: migration-b1-seam | Updated: 2026-10-07 13:20

Structural port only: it declares the execution seam plus read-only identity
methods with the SAME result shapes as the current provider layer. Nothing is
redefined — implementers satisfy the contract by 1:1 delegation over the
existing addon connection (see local_runtime.py), which keeps op_id,
fingerprint, recovery, timeout and quarantine semantics untouched inside the
addon lifecycle manager.

- ``execute`` mirrors ``BlenderConnection.send_command`` 1:1 (same args,
  same result/error dict shapes).
- ``capabilities``/``status`` mirror the provider contract (read-only).
- ``runtime_status`` reports live addon context without mutation.
- ``health`` is read-only liveness without CAD mutation.
- ``backend`` is the controlled escape hatch to the wrapped connection.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class BlenderRuntimePort(Protocol):
    """Seam between the MCP provider layer and Blender execution."""

    @property
    def backend(self) -> Any:
        """Return the wrapped addon connection (controlled escape hatch)."""
        ...

    def execute(
        self,
        op: str,
        params: dict[str, Any] | None = None,
        *,
        rid: str = "unknown",
        timeout_seconds: float = 120.0,
        op_id: str | None = None,
    ) -> dict[str, Any]:
        """Run one addon command; same shapes as BlenderConnection.send_command."""
        ...

    def capabilities(self) -> dict[str, Any]:
        """Return the provider capability map (read-only, no addon contact)."""
        ...

    def status(self) -> dict[str, Any]:
        """Return provider identity + addon reachability (read-only)."""
        ...

    def runtime_status(self) -> dict[str, Any]:
        """Return live addon runtime context (read-only, bounded)."""
        ...

    def health(self) -> dict[str, Any]:
        """Return read-only liveness without CAD mutation."""
        ...
