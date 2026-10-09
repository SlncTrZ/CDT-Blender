# blender_mcp_bridge/remote_runtime.py
"""Remote runtime adapter — B2 split-process path over BlenderRuntimeTransport.

Wing: code | Topic: migration-b2-remote | Updated: 2026-10-07 13:55

Reuses the addon implementation WITHOUT duplication: the workstation agent
owns the exact same B1 adapter/connection stack in its own process, and this
class only forwards typed op names + JSON params over the transport boundary.
No Blender validation, lifecycle, or socket logic lives here — unknown
completion, generation and fencing flow through the same typed errors as the
local path.

Fencing placement (B2): the ONE writer authority is the addon's
MutationLifecycleManager (op_id reservation, payload fingerprint, uncertain
predecessor blocking). This adapter makes exactly ONE dispatch attempt per
``execute`` call and never auto-retries: timeout/disconnect after dispatch
raises completion-unknown and the caller must ``reconcile_operation`` before
any retry with the same op_id.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from . import provider_contract as contract
from .local_runtime import _support_status
from .runtime_port import BlenderRuntimePort
from .runtime_transport import (
    BlenderRuntimeTransport,
    RuntimeGenerationMismatchError,
    RuntimeTransportError,
    RuntimeUnavailableError,
    RuntimeUncertainError,
    check_timeout_ms,
    is_mutation_op,
)


class RemoteBlenderRuntimeAdapter(BlenderRuntimePort):
    """Provider-side adapter: full port contract over a BlenderRuntimeTransport.

    Constructor takes the expected runtime generation observed from the agent
    heartbeat (None pins nothing; a pinned value refuses stale generations
    before trusting results).
    """

    def __init__(
        self,
        transport: BlenderRuntimeTransport,
        *,
        backend_name: str = "addon",
        expected_generation: str | None = None,
        default_timeout_ms: int = 120_000,
    ) -> None:
        if not isinstance(transport, BlenderRuntimeTransport):
            raise TypeError("RemoteBlenderRuntimeAdapter requires a BlenderRuntimeTransport")
        if str(backend_name or "").strip() not in {"addon"}:
            raise ValueError("backend_name must be 'addon'")
        self._transport = transport
        self._backend_name = str(backend_name)
        self._expected_generation = expected_generation
        self._default_timeout_ms = check_timeout_ms(default_timeout_ms)
        self._last_available = False

    # -- port surface --

    @property
    def backend(self) -> Any:
        # No in-process connection exists on this side by design; the addon
        # socket lives in the agent process. Fail closed instead of
        # fabricating a local escape hatch.
        raise RuntimeUnavailableError(
            "remote adapter has no in-process backend; addon execution lives "
            "in the workstation agent process"
        )

    @property
    def expected_generation(self) -> str | None:
        return self._expected_generation

    def pin_generation(self, generation: str) -> None:
        value = str(generation or "").strip()
        if not value:
            raise ValueError("generation pin must be non-empty")
        self._expected_generation = value

    @property
    def generation(self) -> str | None:
        return self._expected_generation

    @property
    def last_available(self) -> bool:
        return self._last_available

    def execute(
        self,
        op: str,
        params: dict[str, Any] | None = None,
        *,
        rid: str = "unknown",
        timeout_seconds: float | None = None,
        op_id: str | None = None,
    ) -> dict[str, Any]:
        """Exactly one dispatch attempt; uncertain loss raises, never replays."""
        timeout_ms = self._default_timeout_ms if timeout_seconds is None else None
        kwargs: dict[str, Any] = {
            "rid": rid,
            "op_id": op_id,
            "expected_generation": self._expected_generation,
        }
        if timeout_seconds is not None:
            kwargs["timeout_seconds"] = timeout_seconds
        elif timeout_ms is not None:
            kwargs["timeout_seconds"] = timeout_ms / 1000.0
        try:
            result = self._transport.call(str(op), params, **kwargs)
        except RuntimeUncertainError:
            # Endpoint answered-or-lost after dispatch may have started.
            # Mutation or not, this call never retries: the caller reconciles.
            self._last_available = True
            raise
        except RuntimeTransportError:
            self._last_available = False
            raise
        self._last_available = True
        if not isinstance(result, dict):
            raise RuntimeTransportError(
                f"remote op {op!r} returned malformed result (not an object)"
            )
        return result

    def capabilities(self) -> dict[str, Any]:
        # Provider contract is identical on both paths; no addon contact.
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
        try:
            agent = self._transport.health()
            reachable = True
        except RuntimeTransportError as exc:
            reachable = False
            agent = {"error": str(exc)}
        binding_ready = reachable and (
            self._expected_generation is None
            or agent.get("generation") == self._expected_generation
        )
        adapter = agent.get("adapter", {})
        native = (
            isinstance(adapter, dict)
            and adapter.get("reachable") is True
            and adapter.get("native_identity_ready", True) is True
        )
        binding_ready = binding_ready and (
            isinstance(adapter, dict) and adapter.get("native_identity_ready", True) is True
        )
        self._last_available = binding_ready and native
        return {
            "status": "ok",
            "binding_ready": binding_ready,
            "agent_reachable": reachable,
            "provider_name": contract.PROVIDER_ID,
            "provider_version": contract.PROVIDER_VERSION,
            "contract_version": contract.CONTRACT_VERSION,
            "transport": "remote",
            "generation": self._expected_generation,
            "addon": {"connected": binding_ready and native, "agent": agent},
        }

    def runtime_status(self) -> dict[str, Any]:
        """Bounded live context through the agent; fail-closed dict when down."""
        try:
            response = self._transport.call(
                "get_runtime_context",
                {},
                rid=f"RUNTIMESTATUS-remote-{uuid4().hex}",
                timeout_seconds=2.0,
                expected_generation=self._expected_generation,
            )
        except RuntimeGenerationMismatchError:
            self._last_available = False
            return {
                "backend_available": False,
                "context_available": False,
                "reason": "generation_mismatch: explicit operator binding required",
            }
        except RuntimeTransportError:
            self._last_available = False
            return {
                "backend_available": False,
                "context_available": False,
                "reason": "runtime_unreachable",
            }
        self._last_available = True
        if (
            not isinstance(response, dict)
            or response.get("status") != "success"
            or not isinstance(response.get("result"), dict)
        ):
            return {
                "backend_available": not (
                    isinstance(response, dict) and response.get("kind") == "provider_unavailable"
                ),
                "context_available": False,
                "reason": "runtime_context_unavailable",
            }
        snapshot = dict(response["result"])
        snapshot["backend_available"] = True
        snapshot["context_available"] = True
        snapshot["runtime_support_status"] = _support_status(snapshot)
        return snapshot

    def health(self) -> dict[str, Any]:
        try:
            agent = self._transport.health()
            reachable = True
        except RuntimeTransportError as exc:
            reachable = False
            agent = {"error": str(exc)}
        self._last_available = reachable
        return {
            "transport": "remote",
            "reachable": reachable,
            "generation": self._expected_generation,
            "provider": contract.PROVIDER_ID,
            "provider_version": contract.PROVIDER_VERSION,
            "mutation_lane": (
                "addon-authoritative: single attempt per execute, "
                "is_mutation_op reflected per op; uncertain loss raises "
                "completion-unknown, blind replay forbidden"
            ),
            "agent": agent,
        }

    def describe_op(self, op: str) -> str:
        kind = "mutation" if is_mutation_op(op) else "read-only"
        return f"{op}: {kind} over remote transport (single attempt, no auto-retry)"
