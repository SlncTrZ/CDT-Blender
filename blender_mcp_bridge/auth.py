# blender_mcp_bridge/auth.py
#
# Fork of seehiong/blender-mcp-bridge (MIT, see ATTRIBUTION.md).
# SlncTrZ provider-shell adaptation by SlncTrZ / Truong Cong Dinh.
#
# Both supported credential forms (Authorization: Bearer / X-API-Key) resolve
# through verify_token() — never through separate logic paths. Fail-closed:
# missing/invalid identity -> 401; valid but denied -> 403. Tokens are never
# logged, echoed, or placed in tool arguments/results.

from __future__ import annotations

import hmac
import os


def expected_token() -> str | None:
    token = (os.getenv("BLENDER_MCP_TOKEN") or "").strip()
    return token or None


def allow_unauthenticated() -> bool:
    return os.getenv("MCP_ALLOW_UNAUTHENTICATED") == "1"


def extract_presented_token(headers: dict[str, str]) -> str | None:
    lowered = {str(k).lower(): v for k, v in headers.items()}
    auth = lowered.get("authorization")
    if isinstance(auth, str):
        scheme, _, credential = auth.partition(" ")
        if scheme.lower() == "bearer" and credential.strip():
            return credential.strip()
    api_key = lowered.get("x-api-key")
    if isinstance(api_key, str) and api_key.strip():
        return api_key.strip()
    return None


def verify_token(headers: dict[str, str]) -> tuple[bool, str]:
    """Return (ok, reason). reason in {"", "missing", "invalid", "forbidden"}."""
    expected = expected_token()
    if not expected:
        # No token configured: closed unless the operator explicitly opted
        # into unauthenticated local testing.
        return (True, "") if allow_unauthenticated() else (False, "missing")
    presented = extract_presented_token(headers)
    if not presented:
        return False, "missing"
    if hmac.compare_digest(presented, expected):
        return True, ""
    return False, "invalid"


def auth_failure_status(reason: str) -> int:
    return 403 if reason == "forbidden" else 401
