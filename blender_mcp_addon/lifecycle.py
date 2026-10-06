"""Mutation lifecycle, stable receipts, and deadline reconciliation for Blender MCP.

Covers BL-01 (stable operation identity + committed/failed/uncertain receipts +
native reconciliation) and BL-02 (expired pending work never starts; started
work exceeding deadline becomes uncertain, not fake-cancelled; dependent writes
block while predecessor is uncertain).
"""

import hashlib
import json
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from typing import Any

READ_ONLY_COMMANDS = frozenset(
    {
        "document_info",
        "object_list",
        "object_get",
        "object_count",
        "organization_list",
        "get_scene_info",
        "get_object_info",
        "get_distance",
        "get_collections",
        "get_keyframes",
        "get_viewport_screenshot",
        "check_mesh_for_printing",
        "get_runtime_context",
        "reconcile_operation",
        "operation_status",
    }
)


class ReceiptState:
    COMMITTED = "committed"
    FAILED = "failed"
    UNCERTAIN = "uncertain"
    EXPIRED_PENDING = "expired_pending"
    IN_FLIGHT = "in_flight"
    PENDING = "pending"
    UNKNOWN = "unknown"


def compute_payload_fingerprint(cmd_type: str, params: dict | None) -> str:
    """Canonical SHA-256 fingerprint of semantic command and parameters."""
    normalized = {"type": str(cmd_type), "params": params or {}}
    try:
        encoded = json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode("utf-8")
    except Exception:
        encoded = str(normalized).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class MutationLifecycleManager:
    """Thread-safe registry for operation receipts and uncertainty gating."""

    def __init__(self, max_receipts: int = 1000):
        self._max_receipts = max_receipts
        self._lock = threading.Lock()
        self._receipts: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._uncertain_ops: set[str] = set()
        self._in_flight: dict[str, float] = {}
        self._pending_ops: set[str] = set()

    def is_mutation(self, cmd_type: str) -> bool:
        if not cmd_type:
            return False
        if cmd_type.startswith("get_"):
            return False
        return cmd_type not in READ_ONLY_COMMANDS

    def has_uncertain(self) -> bool:
        with self._lock:
            return bool(self._uncertain_ops)

    def get_uncertain_ops(self) -> list[str]:
        with self._lock:
            return sorted(self._uncertain_ops)

    def get_receipt(self, op_id: str) -> dict[str, Any] | None:
        with self._lock:
            item = self._receipts.get(op_id)
            return dict(item) if item else None

    def reserve_and_admit(
        self, cmd_type: str, op_id: str, params: dict | None, deadline: float | None
    ) -> tuple[bool, dict[str, Any] | None]:
        """Atomically check admission, fingerprint match, predecessor uncertainty, and reserve pending.

        Returns:
            (admitted, response)
            If admitted is False, response contains the cached result, rejection, or conflict error.
            If admitted is True, the operation is atomically marked PENDING in one critical section.
        """
        fingerprint = compute_payload_fingerprint(cmd_type, params)
        with self._lock:
            # 1. Check existing receipt or active reservation for exact same op_id
            if op_id in self._pending_ops or op_id in self._in_flight or op_id in self._uncertain_ops:
                # Active operations cannot be admitted again
                if op_id in self._pending_ops:
                    return False, {
                        "status": "error",
                        "kind": "duplicate_pending",
                        "retryable": True,
                        "op_id": op_id,
                        "message": f"Operation [{op_id}] is already pending admission in queue.",
                        "receipt": self._receipts.get(op_id),
                    }
                if op_id in self._in_flight:
                    return False, {
                        "status": "error",
                        "kind": "in_flight",
                        "retryable": True,
                        "op_id": op_id,
                        "message": f"Operation [{op_id}] is currently executing in Blender.",
                    }
                if op_id in self._uncertain_ops:
                    return False, {
                        "status": "error",
                        "kind": "timeout_uncertain",
                        "retryable": True,
                        "op_id": op_id,
                        "message": (
                            f"Operation [{op_id}] is in uncertain state. "
                            "Caller must call reconcile_operation before retrying."
                        ),
                        "receipt": self._receipts.get(op_id),
                    }

            if op_id in self._receipts:
                receipt = self._receipts[op_id]
                existing_fp = receipt.get("fingerprint")

                # F11: Payload fingerprint check
                if existing_fp and existing_fp != fingerprint:
                    return False, {
                        "status": "error",
                        "kind": "payload_conflict",
                        "retryable": False,
                        "op_id": op_id,
                        "message": (
                            f"Operation ID [{op_id}] was previously submitted with a different payload fingerprint. "
                            "Cannot reuse same semantic operation ID for a different operation."
                        ),
                        "receipt": dict(receipt),
                    }

                state = receipt.get("state")
                # F02: Pending duplicate rejection
                if state == ReceiptState.PENDING or op_id in self._pending_ops:
                    return False, {
                        "status": "error",
                        "kind": "duplicate_pending",
                        "retryable": True,
                        "op_id": op_id,
                        "message": f"Operation [{op_id}] is already pending admission in queue.",
                        "receipt": dict(receipt),
                    }

                # If operation is committed (even if completed late in background), return cached result!
                if state == ReceiptState.COMMITTED:
                    return False, {
                        "status": "success",
                        "cached": True,
                        "op_id": op_id,
                        "result": receipt.get("result"),
                        "message": f"Cached result for committed operation [{op_id}]. Side effects not duplicated.",
                        "receipt": dict(receipt),
                    }

                # If operation failed (even if failed late in background), return cached failure!
                if state == ReceiptState.FAILED:
                    return False, {
                        "status": "error",
                        "cached": True,
                        "op_id": op_id,
                        "message": receipt.get("message", "Operation previously failed."),
                        "receipt": dict(receipt),
                    }

                if state == ReceiptState.UNCERTAIN or op_id in self._uncertain_ops:
                    return False, {
                        "status": "error",
                        "kind": "timeout_uncertain",
                        "retryable": True,
                        "op_id": op_id,
                        "message": (
                            f"Operation [{op_id}] is in uncertain state. "
                            "Caller must call reconcile_operation before retrying."
                        ),
                        "receipt": dict(receipt),
                    }

                if state == ReceiptState.EXPIRED_PENDING:
                    return False, {
                        "status": "error",
                        "kind": "expired_pending",
                        "retryable": True,
                        "op_id": op_id,
                        "message": f"Operation [{op_id}] expired while pending.",
                        "receipt": dict(receipt),
                    }

            # 2. Check in-flight duplicate
            if op_id in self._in_flight:
                return False, {
                    "status": "error",
                    "kind": "in_flight",
                    "retryable": True,
                    "op_id": op_id,
                    "message": f"Operation [{op_id}] is currently executing in Blender.",
                }

            # 3. Check predecessor uncertainty
            if self.is_mutation(cmd_type) and cmd_type != "reconcile_operation":
                if self._uncertain_ops:
                    predecessors = sorted(self._uncertain_ops)
                    return False, {
                        "status": "error",
                        "kind": "uncertain_predecessor_blocked",
                        "retryable": False,
                        "message": (
                            f"Dependent write blocked: predecessor operation(s) {predecessors} "
                            "are in uncertain state. Call reconcile_operation before dispatching new mutations."
                        ),
                        "uncertain_operations": predecessors,
                    }

            # Atomically reserve pending
            self._pending_ops.add(op_id)
            self._receipts[op_id] = {
                "op_id": op_id,
                "cmd_type": cmd_type,
                "fingerprint": fingerprint,
                "state": ReceiptState.PENDING,
                "enqueued_at": time.time(),
                "deadline": deadline,
            }
            self._trim_receipts()
            return True, None

    def try_start_dispatch(
        self, op_id: str, cmd_type: str, deadline: float | None
    ) -> tuple[bool, dict[str, Any] | None]:
        """H05: Atomically transition an admitted command from PENDING -> IN_FLIGHT.

        Checks:
        1. Deadline check: if now >= deadline, transitions atomically to EXPIRED_PENDING.
        2. Own state: must be PENDING (cannot restart terminal, uncertain, or already in-flight).
        3. Predecessor uncertainty: if any predecessor is UNCERTAIN, transitions to FAILED
           with kind 'uncertain_predecessor_blocked'.

        Returns:
            (can_execute, error_response)
        """
        now = time.monotonic()
        with self._lock:
            # 1. Deadline check before start
            if deadline and now >= deadline:
                self._pending_ops.discard(op_id)
                self._in_flight.pop(op_id, None)
                receipt = self._receipts.get(op_id, {"op_id": op_id})
                receipt["state"] = ReceiptState.EXPIRED_PENDING
                receipt["expired_at"] = now
                receipt["reason"] = f"Expired while pending in queue before dispatch ({now:.3f} >= {deadline:.3f})"
                self._receipts[op_id] = receipt
                return False, {
                    "status": "error",
                    "kind": "expired_pending",
                    "retryable": True,
                    "op_id": op_id,
                    "message": f"Command '{cmd_type}' [{op_id}] expired before dispatch; not started.",
                    "receipt": dict(receipt),
                }

            # 2. Check predecessor uncertainty
            if self.is_mutation(cmd_type) and cmd_type != "reconcile_operation":
                other_uncertain = [u for u in self._uncertain_ops if u != op_id]
                if other_uncertain:
                    self._pending_ops.discard(op_id)
                    receipt = self._receipts.get(op_id, {"op_id": op_id})
                    receipt["state"] = ReceiptState.FAILED
                    receipt["message"] = (
                        f"Predecessor operation(s) {sorted(other_uncertain)} entered uncertain state while queued"
                    )
                    receipt["finished_at"] = now
                    return False, {
                        "status": "error",
                        "kind": "uncertain_predecessor_blocked",
                        "retryable": False,
                        "op_id": op_id,
                        "message": (
                            f"Dependent write blocked at dispatch: predecessor operation(s) {sorted(other_uncertain)} "
                            "entered uncertain state while this command was queued."
                        ),
                        "uncertain_operations": sorted(other_uncertain),
                    }

            # 3. Transition atomically to IN_FLIGHT
            self._pending_ops.discard(op_id)
            self._in_flight[op_id] = now
            if op_id in self._receipts:
                self._receipts[op_id]["state"] = ReceiptState.IN_FLIGHT
                self._receipts[op_id]["started_at"] = now

            return True, None

    def rollback_reservation(self, op_id: str, reason: str = "Admission rejected"):
        """Rollback a pending reservation if enqueuing fails (e.g. queue full).

        Queue saturation is transient: the reservation is removed so a subsequent
        retry with the same semantic op_id can be admitted once queue backlog drains.
        """
        with self._lock:
            self._pending_ops.discard(op_id)
            # Remove pending entry rather than recording terminal FAILED
            self._receipts.pop(op_id, None)

    def can_dispatch_queued(self, op_id: str, cmd_type: str) -> tuple[bool, dict[str, Any] | None]:
        """F03: Verify before dispatch that no predecessor became uncertain while queued."""
        with self._lock:
            if self.is_mutation(cmd_type) and cmd_type != "reconcile_operation":
                # Check if other operations in uncertainty set
                other_uncertain = [u for u in self._uncertain_ops if u != op_id]
                if other_uncertain:
                    return False, {
                        "status": "error",
                        "kind": "uncertain_predecessor_blocked",
                        "retryable": False,
                        "op_id": op_id,
                        "message": (
                            f"Dependent write blocked at dispatch: predecessor operation(s) {sorted(other_uncertain)} "
                            "entered uncertain state while this command was queued."
                        ),
                        "uncertain_operations": sorted(other_uncertain),
                    }
            return True, None

    def record_in_flight(self, op_id: str):
        with self._lock:
            self._pending_ops.discard(op_id)
            self._in_flight[op_id] = time.time()
            if op_id in self._receipts:
                self._receipts[op_id]["state"] = ReceiptState.IN_FLIGHT
                self._receipts[op_id]["started_at"] = time.time()

    def record_committed(self, op_id: str, result: Any):
        with self._lock:
            self._pending_ops.discard(op_id)
            self._in_flight.pop(op_id, None)
            receipt = self._receipts.get(op_id, {"op_id": op_id})
            if op_id in self._uncertain_ops:
                receipt["background_committed"] = True
                receipt["result"] = result
                receipt["finished_at"] = time.time()
                self._receipts[op_id] = receipt
                return

            receipt["state"] = ReceiptState.COMMITTED
            receipt["finished_at"] = time.time()
            receipt["result"] = result
            self._receipts[op_id] = receipt
            self._trim_receipts()

    def record_failed(self, op_id: str, message: str, result: Any = None):
        with self._lock:
            self._pending_ops.discard(op_id)
            self._in_flight.pop(op_id, None)
            receipt = self._receipts.get(op_id, {"op_id": op_id})
            if op_id in self._uncertain_ops:
                receipt["background_failed"] = True
                receipt["message"] = message
                receipt["result"] = result
                receipt["finished_at"] = time.time()
                self._receipts[op_id] = receipt
                return

            receipt["state"] = ReceiptState.FAILED
            receipt["finished_at"] = time.time()
            receipt["message"] = message
            receipt["result"] = result
            self._receipts[op_id] = receipt
            self._trim_receipts()

    def record_uncertain(self, op_id: str, reason: str, cmd_type: str = ""):
        with self._lock:
            self._pending_ops.discard(op_id)
            self._in_flight.pop(op_id, None)
            self._uncertain_ops.add(op_id)
            receipt = self._receipts.get(op_id, {"op_id": op_id, "cmd_type": cmd_type})
            receipt["state"] = ReceiptState.UNCERTAIN
            receipt["uncertain_at"] = time.time()
            receipt["uncertain_reason"] = reason
            self._receipts[op_id] = receipt
            self._trim_receipts()

    def record_expired_pending(self, op_id: str, reason: str):
        with self._lock:
            self._pending_ops.discard(op_id)
            self._in_flight.pop(op_id, None)
            receipt = self._receipts.get(op_id, {"op_id": op_id})
            receipt["state"] = ReceiptState.EXPIRED_PENDING
            receipt["expired_at"] = time.time()
            receipt["reason"] = reason
            self._receipts[op_id] = receipt
            self._trim_receipts()

    def reconcile(
        self,
        op_id: str,
        action: str = "query",
        native_verifier: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Reconcile an operation receipt.

        Action semantics:
        - 'query': Strictly read-only observation. Inspects current state and optionally executes
                   verifier without modifying receipt state or unlocking uncertainty.
        - 'resolve' / 'acknowledge': Reconciles uncertainty if and only if:
                   1) The operation had background_failed -> transitions to FAILED and unlocks.
                   2) The operation had background_committed or native verification succeeded ->
                      transitions to COMMITTED and unlocks.
                   If verification failed or was inconclusive, uncertainty persists.
        """
        with self._lock:
            receipt = self._receipts.get(op_id)
            if not receipt:
                return {
                    "status": "error",
                    "op_id": op_id,
                    "state": ReceiptState.UNKNOWN,
                    "message": f"No receipt found for operation [{op_id}].",
                    "uncertain_operations": sorted(self._uncertain_ops),
                }

            native_report = None
            if native_verifier is not None:
                try:
                    native_report = native_verifier(receipt)
                except Exception as exc:
                    native_report = {"verified": False, "error": str(exc)}

            # Query mode: strictly read-only snapshot observation
            if action not in ("resolve", "acknowledge", "clear"):
                return {
                    "status": "success",
                    "op_id": op_id,
                    "state": receipt.get("state"),
                    "receipt": dict(receipt),
                    "native_verification": native_report,
                    "uncertain_operations": sorted(self._uncertain_ops),
                }

            # Resolve / Acknowledge: determine definitive outcome
            resolved_state = None
            if receipt.get("background_failed"):
                # Definite failure confirmed: preserve failure, never promote to committed!
                resolved_state = ReceiptState.FAILED
            elif receipt.get("background_committed") and (
                native_report is None or native_report.get("verified")
            ):
                resolved_state = ReceiptState.COMMITTED
            elif native_report and native_report.get("verified"):
                resolved_state = ReceiptState.COMMITTED

            if resolved_state is not None:
                receipt["state"] = resolved_state
                receipt["reconciled_at"] = time.time()
                receipt["reconcile_action"] = action
                self._uncertain_ops.discard(op_id)

            return {
                "status": "success",
                "op_id": op_id,
                "state": receipt.get("state"),
                "receipt": dict(receipt),
                "native_verification": native_report,
                "uncertain_operations": sorted(self._uncertain_ops),
            }

    def _trim_receipts(self):
        while len(self._receipts) > self._max_receipts:
            for oldest_k in list(self._receipts.keys()):
                # Protected capacity: NEVER evict PENDING, IN_FLIGHT, or UNCERTAIN operations
                if (
                    oldest_k not in self._uncertain_ops
                    and oldest_k not in self._in_flight
                    and oldest_k not in self._pending_ops
                ):
                    self._receipts.pop(oldest_k)
                    break
            else:
                break
