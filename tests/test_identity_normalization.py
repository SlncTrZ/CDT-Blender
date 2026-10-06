"""H07: response normalization preserves operation identity on every outcome.

A caller that times out on a mutation must be able to recover by op_id. Cached,
conflict, and typed-error receipts echo op_id from the addon; the first-execution
success/error path does not, so the bridge attaches the effective op_id there.
First and cached outcomes must share the same identity field.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from blender_mcp_bridge.server import _attach_mutation_identity, _normalize_result  # noqa: E402


def test_first_execution_success_gets_identity_attached():
    """First-execution success lacks op_id from the addon; the bridge must add it."""
    result = {"status": "success", "result": {"name": "Cube"}}
    _, _, normalized = _normalize_result("create_cube", result)
    normalized = _attach_mutation_identity("create_cube", normalized, "op-first", "RID123")
    assert normalized["op_id"] == "op-first"


def test_effective_identity_falls_back_to_rid():
    """With no caller op_id, the effective identity is the correlation id."""
    result = {"status": "success", "result": {"name": "Cube"}}
    _, _, normalized = _normalize_result("create_cube", result)
    normalized = _attach_mutation_identity("create_cube", normalized, None, "RID123")
    assert normalized["op_id"] == "RID123"


def test_cached_outcome_keeps_addon_op_id():
    """A cached/conflict receipt already carries op_id — never overwrite it."""
    result = {"status": "success", "op_id": "cached-op", "cached": True}
    _, _, normalized = _normalize_result("create_cube", result)
    normalized = _attach_mutation_identity("create_cube", normalized, "op-new", "RID123")
    assert normalized["op_id"] == "cached-op"


def test_cached_envelope_flattens_with_identity():
    """First and cached outcomes share the same op_id field after flattening."""
    cached_env = {
        "status": "success",
        "result": {"name": "Cube"},
        "op_id": "op-cached",
        "cached": True,
    }
    _, _, normalized = _normalize_result("create_cube", cached_env)
    normalized = _attach_mutation_identity("create_cube", normalized, "op-cached", "RID123")
    assert normalized["op_id"] == "op-cached"
    assert normalized["cached"] is True


def test_read_only_query_gets_no_identity():
    """Read-only queries have nothing to reconcile; do not inject op_id."""
    result = {"status": "success", "result": {"objects": []}}
    _, _, normalized = _normalize_result("object_list", result)
    normalized = _attach_mutation_identity("object_list", normalized, None, "RID123")
    assert "op_id" not in normalized


def test_recovery_tool_is_not_treated_as_mutation():
    """reconcile_operation carries its own target op_id and must not be overwritten."""
    result = {"status": "success", "op_id": "target-op", "state": "committed"}
    _, _, normalized = _normalize_result("reconcile_operation", result)
    normalized = _attach_mutation_identity(
        "reconcile_operation", normalized, "recovery-RID123", "RID123"
    )
    assert normalized["op_id"] == "target-op"
