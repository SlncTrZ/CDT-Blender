"""Guard L2 validation typing without changing unrelated addon tool errors."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from blender_mcp_bridge.tools.infographic import get_infographic_tools

ROOT = Path(__file__).resolve().parents[1]


def _load():
    path = ROOT / "blender_mcp_addon" / "infographic_errors.py"
    spec = importlib.util.spec_from_file_location("_isolated_l2_errors", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_native_l2_errors_match_all_public_l2_schemas():
    mod = _load()
    assert mod.L2_TOOL_NAMES == {t.name for t in get_infographic_tools()}


def test_l2_value_errors_are_typed_non_retryable():
    mod = _load()
    for name in mod.L2_TOOL_NAMES:
        assert mod.validation_refusal(name, ValueError("over budget")) == {
            "status": "error",
            "kind": "validation_error",
            "retryable": False,
            "message": "over budget",
        }


def test_existing_tools_and_unexpected_failures_keep_prior_behavior():
    mod = _load()
    assert mod.validation_refusal("create_cube", ValueError("bad cube")) is None
    assert (
        mod.validation_refusal("create_animated_particle_grid", RuntimeError("native issue"))
        is None
    )
    assert mod.validation_refusal("document_open", FileNotFoundError("missing")) is None


def test_server_applies_typing_at_native_exception_boundary():
    text = (ROOT / "blender_mcp_addon/server.py").read_text(encoding="utf-8")
    assert "from .infographic_errors import validation_refusal" in text
    assert "typed = validation_refusal(cmd_type, e)" in text
    assert "if typed is not None:" in text
