# blender_mcp_bridge/provider_contract.py
#
# Fork of seehiong/blender-mcp-bridge (MIT, see ATTRIBUTION.md).
# SlncTrZ provider-shell adaptation by SlncTrZ / Truong Cong Dinh.
#
# Single source of truth for the stable provider identity, versioning and
# capability declarations required by specs/MCP_PROVIDER_STANDARD.md, so the
# help, status and HTTP layers can never drift apart.

from __future__ import annotations

import hashlib
import os

PROVIDER_ID = "blender"

# Must track pyproject.toml.
PROVIDER_VERSION = "0.1.3+cdt.1"

# Bump on any tool/capability change.
CONTRACT_VERSION = "cdt-blender-contract-v7"

# Applied CDT common semantics (subset claim — see CAPABILITIES).
COMMON_CONTRACT_VERSION = "cdt-common-v1"

# MCP protocol / SDK compatibility declaration.
PROTOCOL_VERSION = "MCP 2025-06-18 / mcp-py 1.x Streamable HTTP (stateless)"

ERROR_KINDS = [
    "authentication_error",
    "authorization_error",
    "validation_error",
    "not_found",
    "conflict",
    "rate_limited",
    "timeout",
    "provider_unavailable",
    "internal_error",
    "unsupported_capability",
]

# Honest capability map. Unsupported entries MUST fail with a typed refusal
# (status "error" + kind "unsupported_capability"), never fake success.
# Sculpting notes: the provider ships deterministic assists (smooth/inflate/
# grab/symmetrize/dyntopo toggle). Brush strokes, masks, face sets and
# multiresolution stay unsupported until proven in a valid sculpt context.
CAPABILITIES: dict[str, dict[str, str | bool]] = {
    "common.document.new": {"supported": True, "mode": "native"},
    "common.document.open": {"supported": True, "mode": "native"},
    "common.document.info": {"supported": True, "mode": "native"},
    "common.document.save": {"supported": True, "mode": "native"},
    "common.document.save_as": {"supported": True, "mode": "native"},
    "common.document.close": {"supported": True, "mode": "native"},
    "common.object.list": {"supported": True, "mode": "native"},
    "common.object.get": {"supported": True, "mode": "native"},
    "common.object.count": {"supported": True, "mode": "native"},
    "common.organization.list": {"supported": True, "mode": "native"},
    "common.transform.move": {"supported": True, "mode": "native"},
    "common.transform.rotate": {"supported": True, "mode": "native"},
    "common.transform.scale": {"supported": True, "mode": "native"},
    "common.transaction.begin": {
        "supported": False,
        "mode": "unsupported",
        "reason": "no_atomic_transaction_use_undo_history",
    },
    "common.transaction.commit": {
        "supported": False,
        "mode": "unsupported",
        "reason": "no_atomic_transaction_use_undo_history",
    },
    "common.transaction.rollback": {
        "supported": False,
        "mode": "unsupported",
        "reason": "no_atomic_transaction_use_undo_history",
    },
    "common.undo": {"supported": True, "mode": "native"},
    "common.redo": {"supported": True, "mode": "native"},
    "common.import_asset": {"supported": True, "mode": "native"},
    "common.export_asset": {"supported": True, "mode": "native"},
    "common.validate.document": {"supported": True, "mode": "native"},
    "common.inspect.object": {"supported": True, "mode": "native"},
    "common.measure.bounds": {"supported": True, "mode": "native"},
    "blender.modeling.mesh_edit": {"supported": True, "mode": "native"},
    "blender.modeling.modifiers": {"supported": True, "mode": "native"},
    "blender.modeling.uv": {
        "supported": False,
        "mode": "unsupported",
        "reason": "no_uv_unwrap_tool_yet",
    },
    "blender.sculpt.assist": {"supported": True, "mode": "native"},
    "blender.sculpt.brush_strokes": {
        "supported": False,
        "mode": "unsupported",
        "reason": "strokes_need_interactive_sculpt_context",
    },
    "blender.sculpt.masks": {
        "supported": False,
        "mode": "unsupported",
        "reason": "no_mask_tools_yet",
    },
    "blender.sculpt.face_sets": {
        "supported": False,
        "mode": "unsupported",
        "reason": "no_face_set_tools_yet",
    },
    "blender.sculpt.multires": {
        "supported": False,
        "mode": "unsupported",
        "reason": "no_multires_workflow_yet",
    },
    "blender.scene.render": {"supported": True, "mode": "native"},
    "blender.interchange.fbx": {"supported": True, "mode": "native"},
    "blender.interchange.gltf": {"supported": True, "mode": "native"},
}

# Wheel builds bundle a snapshot at blender_mcp_bridge/data/TOOL_GUIDE.md (see
# pyproject force-include); repo checkouts read docs/TOOL_GUIDE.md live so
# guide edits land without reinstalling.
_GUIDE_CANDIDATES = (
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "TOOL_GUIDE.md"
    ),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "TOOL_GUIDE.md"),
    os.path.join(os.getcwd(), "docs", "TOOL_GUIDE.md"),
)


def guide_path() -> str | None:
    for candidate in _GUIDE_CANDIDATES:
        if os.path.isfile(candidate):
            return candidate
    return None


def read_guide() -> str:
    path = guide_path()
    if not path:
        return ""
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def contract_hash(content: str | None = None) -> str:
    canonical = (content if content is not None else read_guide()).replace("\r\n", "\n")
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
