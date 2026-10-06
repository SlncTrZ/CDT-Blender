"""Mutation lifecycle, stable receipts, and deadline reconciliation for Blender MCP.

Covers BL-01 (stable operation identity + committed/failed/uncertain receipts +
native reconciliation) and BL-02 (expired pending work never starts; started
work exceeding deadline becomes uncertain, not fake-cancelled; dependent writes
block while predecessor is uncertain).
"""

from collections import OrderedDict
from collections.abc import Callable
import threading
import time
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
    UNKNOWN = "unknown"


class MutationLifecycleManager:
    """Thread-safe registry for operation receipts and uncertainty gating."""

    def __init__(self, max_receipts: int = 1000):
        self._max_receipts = max_receipts
        self._lock = threading.Lock()
        self._receipts: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._uncertain_ops: set[str] = set()
        self._in_flight: dict[str, float] = {}

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

    def check_admission(self, cmd_type: str, op_id: str) -> dict[str, Any] | None:
        """Pre-enqueue check for idempotency and predecessor uncertainty.

        Returns None if command can proceed to enqueue.
        Returns response dict if command is rejected or short-circuited.
        """
        with self._lock:
            # 1. Check cached receipt for exact same op_id
            if op_id in self._receipts:
                receipt = self._receipts[op_id]
                state = receipt.get("state")
                if state == ReceiptState.COMMITTED and not receipt.get("background_committed"):
                    return {
                        "status": "success",
                        "cached": True,
                        "op_id": op_id,
                        "result": receipt.get("result"),
                        "message": f"Cached result for committed operation [{op_id}]. Side effects not duplicated.",
                        "receipt": dict(receipt),
                    }
                if state == ReceiptState.FAILED and not receipt.get("background_failed"):
                    return {
                        "status": "error",
                        "cached": True,
                        "op_id": op_id,
                        "message": receipt.get("message", "Operation previously failed."),
                        "receipt": dict(receipt),
                    }
                if state == ReceiptState.UNCERTAIN or op_id in self._uncertain_ops:
                    return {
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
                    return {
                        "status": "error",
                        "kind": "expired_pending",
                        "retryable": True,
                        "op_id": op_id,
                        "message": f"Operation [{op_id}] expired while pending.",
                        "receipt": dict(receipt),
                    }

            # 2. Check in-flight duplicate
            if op_id in self._in_flight:
                return {
                    "status": "error",
                    "kind": "in_flight",
                    "retryable": True,
                    "op_id": op_id,
                    "message": f"Operation [{op_id}] is currently executing in Blender.",
                }

            # 3. If mutation, check predecessor uncertainty
            if self.is_mutation(cmd_type) and cmd_type != "reconcile_operation":
                if self._uncertain_ops:
                    predecessors = sorted(self._uncertain_ops)
                    return {
                        "status": "error",
                        "kind": "uncertain_predecessor_blocked",
                        "retryable": False,
                        "message": (
                            f"Dependent write blocked: predecessor operation(s) {predecessors} "
                            "are in uncertain state. Call reconcile_operation before dispatching new mutations."
                        ),
                        "uncertain_operations": predecessors,
                    }

        return None

    def record_pending(self, op_id: str, cmd_type: str, params: dict, deadline: float | None):
        with self._lock:
            self._receipts[op_id] = {
                "op_id": op_id,
                "cmd_type": cmd_type,
                "state": "pending",
                "enqueued_at": time.time(),
                "deadline": deadline,
            }
            self._trim_receipts()

    def record_in_flight(self, op_id: str):
        with self._lock:
            self._in_flight[op_id] = time.time()
            if op_id in self._receipts:
                self._receipts[op_id]["state"] = ReceiptState.IN_FLIGHT
                self._receipts[op_id]["started_at"] = time.time()

    def record_committed(self, op_id: str, result: Any):
        with self._lock:
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
        """Reconcile an operation receipt and optionally clear its uncertainty."""
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

            if action in ("acknowledge", "clear", "resolve"):
                self._uncertain_ops.discard(op_id)
                receipt["reconciled_at"] = time.time()
                receipt["reconcile_action"] = action
                if receipt.get("background_committed") or (native_report and native_report.get("verified")):
                    receipt["state"] = ReceiptState.COMMITTED
                elif receipt.get("background_failed"):
                    receipt["state"] = ReceiptState.FAILED

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
                if oldest_k not in self._uncertain_ops and oldest_k not in self._in_flight:
                    self._receipts.pop(oldest_k)
                    break
            else:
                break
