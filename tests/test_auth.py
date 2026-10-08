"""Authentication regression tests.
Wing: blender | Topic: provider-auth | Updated: 2026-09-14 20:40
"""

from __future__ import annotations

import secrets

from blender_mcp_bridge import auth


def test_auth_fails_closed_without_configured_identity(monkeypatch):
    monkeypatch.delenv("BLENDER_MCP_TOKEN", raising=False)
    monkeypatch.delenv("MCP_ALLOW_UNAUTHENTICATED", raising=False)

    ok, reason = auth.verify_token({})

    assert ok is False
    assert reason == "missing"
    assert auth.auth_failure_status(reason) == 401


def test_configured_identity_rejects_missing_and_invalid_then_accepts_bearer(monkeypatch):
    expected = secrets.token_urlsafe(24)
    invalid = secrets.token_urlsafe(24)
    monkeypatch.setenv("BLENDER_MCP_TOKEN", expected)
    monkeypatch.setenv("MCP_ALLOW_UNAUTHENTICATED", "1")

    assert auth.verify_token({}) == (False, "missing")
    assert auth.verify_token({"Authorization": f"Bearer {invalid}"}) == (False, "invalid")
    assert auth.verify_token({"Authorization": f"Bearer {expected}"}) == (True, "")


def test_compatibility_api_key_uses_same_authorization_layer(monkeypatch):
    expected = secrets.token_urlsafe(24)
    monkeypatch.setenv("BLENDER_MCP_TOKEN", expected)
    monkeypatch.delenv("MCP_ALLOW_UNAUTHENTICATED", raising=False)

    assert auth.verify_token({"X-API-Key": expected}) == (True, "")


def test_local_unauthenticated_opt_in_only_applies_when_no_identity_is_configured(monkeypatch):
    monkeypatch.delenv("BLENDER_MCP_TOKEN", raising=False)
    monkeypatch.setenv("MCP_ALLOW_UNAUTHENTICATED", "1")
    assert auth.verify_token({}) == (True, "")

    monkeypatch.setenv("BLENDER_MCP_TOKEN", secrets.token_urlsafe(24))
    assert auth.verify_token({}) == (False, "missing")


def test_forbidden_reason_maps_to_403():
    assert auth.auth_failure_status("forbidden") == 403
