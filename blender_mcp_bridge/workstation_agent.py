# blender_mcp_bridge/workstation_agent.py
"""Workstation-side Blender runtime agent — minimal B2 executor.

Wing: code | Topic: migration-b2-agent | Updated: 2026-10-07 13:50

Authenticated persistent listener that owns the workstation execution side of
the RuntimeTransport boundary. Scope is deliberately minimal:

- bearer-authenticated HTTP listener (loopback by default) + heartbeat;
- runtime generation minted at agent start (restart creates a new one);
- process/session discovery (pid; Blender sessions are owned by the addon);
- approved addon attachment = the injected B1 adapter that reuses the
  current local-socket connection implementation;
- bounded adapter dispatch by op name from the shared allowlist.

The addon speaks only its existing local socket, and only with this agent's
adapter: no new addon protocol, no LAN addon exposure, no MCP server here,
no engineering semantics, and — critically — NO lifecycle manager.
Writer authority (op_id reservation, fingerprint, uncertainty gating) stays
inside the addon's MutationLifecycleManager; the agent only serializes
dispatch with a plain lock so transport interleaving cannot overlap two
native calls. Uncertainty decisions flow back to the provider over the wire.
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from .runtime_transport import (
    MAX_REQUEST_BYTES,
    MAX_RESPONSE_BYTES,
    bearer_matches,
    check_op,
    check_timeout_ms,
    is_mutation_op,
)

_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})

# Grace added to the agent-side join so the addon's own typed timeouts
# (COMMAND_WAIT_TIMEOUT 60s, bridge transport deadline) normally win and flow
# back as typed result dicts. Only a hung dispatch past this bound becomes an
# agent-level dispatch_timeout_uncertain envelope.
_DISPATCH_GRACE_SECONDS = 2.0


def _current_process_session() -> dict[str, Any]:
    return {"pid": os.getpid()}


def _adapter_health_summary(adapter: Any) -> dict[str, Any]:
    try:
        health = adapter.health()
        return health if isinstance(health, dict) else {"detail": str(health)}
    except Exception as exc:
        return {"available": False, "error": str(exc)}


@dataclass
class WorkstationAgentConfig:
    host: str = "127.0.0.1"
    port: int = 0  # 0 = ephemeral; actual port read back after start
    auth_token: str = ""
    allow_remote_bind: bool = False
    max_request_bytes: int = MAX_REQUEST_BYTES

    def __post_init__(self) -> None:
        if not str(self.auth_token or "").strip():
            raise ValueError("WorkstationBlenderRuntimeAgent requires a non-empty auth_token")
        if self.host.lower() not in _LOOPBACK_HOSTS and not self.allow_remote_bind:
            raise ValueError(
                f"refusing non-loopback agent bind {self.host!r} without allow_remote_bind"
            )
        if not 0 <= self.port <= 65535:
            raise ValueError("port must be within [0, 65535]")
        if self.max_request_bytes <= 0:
            raise ValueError("max_request_bytes must be > 0")


class _AgentHandler(BaseHTTPRequestHandler):
    """HTTP front for one WorkstationBlenderRuntimeAgent (thin I/O, no CAD).

    The owning agent is reached through ``self.server.agent`` (set by
    ``start`` on its own server instance), so concurrent agents never share
    handler state. All routing decisions live in agent methods, which are
    directly unit-testable without sockets.
    """

    server_version = "CDT-WorkstationBlenderAgent/0.1"

    @property
    def _agent(self) -> WorkstationBlenderRuntimeAgent:
        return self.server.agent  # type: ignore[attr-defined]

    def _send(self, status: int, payload: dict[str, Any]) -> None:
        override, raw = WorkstationBlenderRuntimeAgent.encode_body(payload)
        if override is not None:
            status = override
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        try:
            self.wfile.write(raw)
        except OSError:
            pass  # client went away (e.g. transport deadline fired first);
            # the uncertainty is already fail-closed on the provider side.

    def _refuse_auth(self) -> None:
        agent = self._agent
        self._send(
            401,
            agent._envelope(False, None, "unauthorized", "invalid bearer token", False),
        )

    def _read_body(self) -> tuple[int | None, Any]:
        """Read+parse the POST body. Returns (error_status_or_None, body)."""
        agent = self._agent
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > agent._config.max_request_bytes:
            return 400, agent._envelope(
                False, None, "oversized", "request body missing or oversized", False
            )
        try:
            return None, json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError):
            return 400, agent._envelope(False, None, "bad_request", "malformed JSON body", False)

    def do_GET(self) -> None:  # noqa: N802 — stdlib handler naming
        agent = self._agent
        if not agent.check_bearer(self.headers.get("Authorization", "")):
            self._refuse_auth()
            return
        status, payload = agent.handle_get(self.path)
        self._send(status, payload)

    def do_POST(self) -> None:  # noqa: N802 — stdlib handler naming
        agent = self._agent
        if not agent.check_bearer(self.headers.get("Authorization", "")):
            self._refuse_auth()
            return
        error_status, body = self._read_body()
        if error_status is not None:
            self._send(error_status, body)
            return
        status, payload = agent.handle_post(self.path, body)
        self._send(status, payload)

    def log_message(self, *args: Any) -> None:
        pass  # quiet by design; heartbeat/discovery carry observability


class WorkstationBlenderRuntimeAgent:
    """Owns one B1 adapter + one runtime generation behind an authed listener."""

    def __init__(self, adapter: Any, config: WorkstationAgentConfig) -> None:
        from .runtime_port import BlenderRuntimePort

        if not isinstance(adapter, BlenderRuntimePort):
            raise TypeError("WorkstationBlenderRuntimeAgent requires a BlenderRuntimePort adapter")
        self._adapter = adapter
        self._config = config
        self._generation = f"gen-{uuid4().hex}"
        self._started_at = time.time()
        self._dispatch_lock = threading.Lock()  # serializes native dispatch only
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._session = _current_process_session()

    @property
    def generation(self) -> str:
        return self._generation

    @property
    def adapter(self) -> Any:
        return self._adapter

    @property
    def base_url(self) -> str:
        if self._server is None:
            raise RuntimeError("agent is not started")
        host, port = self._server.server_address[:2]
        if isinstance(host, bytes):
            host = host.decode("ascii")
        return f"http://{host}:{port}"

    # -- runtime surface (no engineering semantics) --

    def heartbeat(self) -> dict[str, Any]:
        return {
            "generation": self._generation,
            "uptime_s": round(time.time() - self._started_at, 3),
            "session": dict(self._session),
            "adapter": _adapter_health_summary(self._adapter),
        }

    def dispatch(
        self,
        op: str,
        params: dict[str, Any] | None = None,
        *,
        rid: str = "unknown",
        timeout_ms: int | None = None,
        op_id: str | None = None,
        expected_generation: str | None = None,
    ) -> dict[str, Any]:
        """Run one allowlisted adapter op and wrap it in the wire envelope."""
        try:
            name = check_op(op)
        except ValueError as exc:
            return self._envelope(False, None, "unknown_op", str(exc), False)
        if expected_generation is not None and expected_generation != self._generation:
            # Wrong generation refuses BEFORE touching Blender.
            return self._envelope(
                False,
                None,
                "generation_mismatch",
                f"stale runtime generation: expected {expected_generation!r}, "
                f"agent generation is {self._generation!r}",
                False,
            )
        try:
            bound_ms = check_timeout_ms(timeout_ms)
        except ValueError as exc:
            return self._envelope(False, None, "bad_request", str(exc), False)
        target = getattr(self._adapter, "execute", None)
        if not callable(target):
            return self._envelope(
                False, None, "unknown_op", "adapter has no execute surface", False
            )
        # Non-authoritative serialization: prevents transport overlap only.
        # Writer authority + uncertainty gating stay addon-side.
        with self._dispatch_lock:
            try:
                result = self._run_bounded(target, name, dict(params or {}), rid, bound_ms, op_id)
            except TimeoutError as exc:
                # Deadline fired after dispatch started: completion unknown.
                # Mutation or not, the caller must reconcile, never blind-retry
                # a mutation; reads may simply retry with a fresh rid.
                return self._envelope(False, None, "dispatch_timeout_uncertain", str(exc), True)
            except Exception as exc:
                uncertain = bool(getattr(exc, "completion_unknown", False))
                code = "uncertain" if uncertain else "backend_error"
                return self._envelope(False, None, code, str(exc), uncertain)
        if not isinstance(result, dict):
            return self._envelope(
                False, None, "backend_error", "adapter returned malformed result", False
            )
        return self._envelope(True, result, "ok", "", False)

    def _envelope(
        self,
        ok: bool,
        result: Any,
        code: str,
        message: str,
        completion_unknown: bool,
    ) -> dict[str, Any]:
        return {
            "ok": ok,
            "result": result,
            "error_code": code,
            "error_message": message,
            "generation": self._generation,
            "completion_unknown": completion_unknown,
        }

    @staticmethod
    def _run_bounded(
        execute: Any,
        op: str,
        params: dict[str, Any],
        rid: str,
        bound_ms: int,
        op_id: str | None,
    ) -> Any:
        """Run the adapter execute with a hard deadline (worker thread)."""
        outcome: dict[str, Any] = {}

        def _invoke() -> None:
            try:
                outcome["result"] = execute(
                    op, params, rid=rid, timeout_seconds=bound_ms / 1000.0, op_id=op_id
                )
            except BaseException as exc:  # noqa: BLE001 — transported, not interpreted
                outcome["error"] = exc

        worker = threading.Thread(target=_invoke, daemon=True)
        worker.start()
        worker.join(timeout=bound_ms / 1000.0 + _DISPATCH_GRACE_SECONDS)
        if worker.is_alive():
            raise TimeoutError(
                f"adapter op {op!r} exceeded {bound_ms}ms after dispatch; "
                "completion is unknown, blind retry is forbidden"
            )
        if "error" in outcome:
            raise outcome["error"]
        return outcome.get("result")

    # -- listener lifecycle --

    def check_bearer(self, presented: str) -> bool:
        """Validate an Authorization header value (constant-time, never logged)."""
        scheme, _, token = (presented or "").partition(" ")
        if scheme.lower() != "bearer":
            return False
        return bearer_matches(token.strip(), self._config.auth_token)

    def handle_get(self, path: str) -> tuple[int, dict[str, Any]]:
        """Route one authenticated GET; pure routing, no socket I/O."""
        route = (urlparse(path).path.rstrip("/") or "/").lower()
        if route in ("/health", "/heartbeat"):
            return 200, self._envelope(True, self.heartbeat(), "ok", "", False)
        if route == "/status":
            try:
                adapter_status: Any = self._adapter.runtime_status()
            except Exception as exc:
                adapter_status = {"error": str(exc)}
            return 200, self._envelope(
                True,
                {"heartbeat": self.heartbeat(), "adapter_status": adapter_status},
                "ok",
                "",
                False,
            )
        return 404, self._envelope(False, None, "not_found", f"no route: {route}", False)

    def handle_post(self, path: str, body: Any) -> tuple[int, dict[str, Any]]:
        """Route one authenticated POST body; pure routing, no socket I/O."""
        route = (urlparse(path).path.rstrip("/") or "/").lower()
        if route != "/dispatch":
            return 404, self._envelope(False, None, "not_found", f"no route: {route}", False)
        if not isinstance(body, dict):
            return 400, self._envelope(False, None, "bad_request", "body must be an object", False)
        envelope = self.dispatch(
            body.get("op", ""),
            body.get("params"),
            rid=body.get("rid", "unknown"),
            timeout_ms=body.get("timeout_ms"),
            op_id=body.get("op_id"),
            expected_generation=body.get("expected_generation"),
        )
        if envelope.get("error_code") in ("unknown_op", "bad_request"):
            return 400, envelope
        return 200, envelope

    @staticmethod
    def encode_body(payload: dict[str, Any]) -> tuple[int | None, bytes]:
        """Encode a wire envelope; oversized results force a 500 envelope.

        Returns (status_override_or_None, raw_bytes): None keeps the caller's
        status, an int replaces it (oversized fallback).
        """
        raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        if len(raw) > MAX_RESPONSE_BYTES:
            fallback = {
                "ok": False,
                "result": None,
                "error_code": "oversized",
                "error_message": "response oversized",
                "generation": str(payload.get("generation") or "unbound"),
                "completion_unknown": False,
            }
            return 500, json.dumps(fallback, separators=(",", ":")).encode("utf-8")
        return None, raw

    def start(self) -> str:
        if self._server is not None:
            raise RuntimeError("agent is already started")
        server = ThreadingHTTPServer((self._config.host, self._config.port), _AgentHandler)
        server.daemon_threads = True
        # Per-instance owner (never shared across agents).
        server.agent = self  # type: ignore[attr-defined]
        self._server = server
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05})
        thread.daemon = True
        thread.start()
        self._thread = thread
        return self.base_url

    def stop(self) -> None:
        server, thread = self._server, self._thread
        self._server = None
        self._thread = None
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=5.0)


def describe_context_requirement(op: str) -> str:
    """Human-readable lane hint for an op (observability only, no enforcement)."""
    if not is_mutation_op(op):
        return "read-only: no Blender context mutation"
    return "mutation: valid Blender context required; reconcile on uncertainty"
