# blender_mcp_bridge/runtime_transport.py
"""Blender runtime transport — provider/execution boundary for migration B2.

Wing: code | Topic: migration-b2-transport | Updated: 2026-10-07 13:40

Typed bounded request/response between the MCP provider process and the
workstation-side Blender runtime agent. Two implementations share one contract:

- ``LocalBlenderRuntimeTransport`` — in-process delegate over a
  BlenderRuntimePort (B1 adapter). Default single-host path; behavior
  unchanged (no allowlist re-validation locally: the addon remains the
  authority for unknown commands, exactly as on the direct provider path).
- ``RemoteBlenderRuntimeTransport`` — loopback HTTP client to a
  WorkstationBlenderRuntimeAgent (see workstation_agent.py). Proves the
  split-process path on one host; split-host deploy comes later.

This module owns NO Blender semantics: the only operation vocabulary is the
``ALLOWED_OPS`` allowlist of addon command names (source of truth:
``blender_mcp_addon/server.py`` ``execute_command`` dispatcher). Payloads are
opaque JSON primitives dispatched by name. op_id/fingerprint/recovery
semantics stay inside the reused addon lifecycle manager behind the B1 port.

Fencing note (B2): the single mutation-writer authority stays addon-side
(one MutationLifecycleManager per addon process: duplicate_pending,
in_flight, payload_conflict, uncertain_predecessor_blocked). The workstation
agent holds NO lifecycle manager — only a non-authoritative serial dispatch
lock that prevents transport interleaving. Uncertainty decisions made by the
addon flow back to the provider over the wire; transport loss after dispatch
is completion-unknown and blind replay stays forbidden.

Sync API by design: ``BlenderConnection.send_command`` is blocking and the
provider already offloads it with ``asyncio.to_thread``; the transports keep
the same shape so the seam adds no new concurrency model.
"""

from __future__ import annotations

import hmac
import json
import socket
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from .connection import BLENDER_TRANSPORT_TIMEOUT_SECONDS

_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})

# Single source of truth for the dispatch vocabulary. Names only — no arg
# shapes, no validation, no Blender meaning. Mirrors the addon
# ``execute_command`` dispatcher in blender_mcp_addon/server.py. Imported by
# the agent (refuse unknown before CAD), the remote transport and the remote
# adapter. Provider-local tools (help/system_*/design-rule lookups) never
# reach this boundary.
ALLOWED_OPS: frozenset[str] = frozenset(
    {
        # runtime discovery / lifecycle recovery (internal bridge commands)
        "get_runtime_context",
        "reconcile_operation",
        "operation_status",
        # common document lifecycle
        "document_new",
        "document_open",
        "document_info",
        "document_save",
        "document_save_as",
        "document_close",
        # common object query / organization
        "object_list",
        "object_get",
        "object_count",
        "organization_list",
        # common object transforms
        "object_move",
        "object_rotate",
        "object_scale",
        # scene
        "get_scene_info",
        "get_object_info",
        "get_viewport_screenshot",
        "get_distance",
        # collections
        "create_collection",
        "set_active_collection",
        "move_to_collection",
        "get_collections",
        "remove_collection",
        "duplicate_collection",
        "set_collection_visibility",
        # modeling (primitives / curves / operators / modifiers / UV)
        "create_primitive",
        "create_cube",
        "create_cylinder",
        "create_sphere",
        "create_cone",
        "create_icosphere",
        "create_torus",
        "create_text",
        "create_plane",
        "create_empty",
        "create_polygon",
        "create_watertight_plate",
        "create_curve",
        "extract_sketch",
        "duplicate_object",
        "duplicate_selection",
        "create_and_array",
        "batch_transform",
        "apply_modifier",
        "copy_modifier",
        "remove_modifier",
        "boolean_operation",
        "apply_all_modifiers",
        "transform_object",
        "circular_array",
        "select_objects",
        "select_by_pattern",
        "select_by_collection",
        "delete_object",
        "set_object_dimensions",
        "join_objects",
        "random_distribute",
        "apply_transforms",
        "extrude_mesh",
        "inset_faces",
        "shear_mesh",
        "invert_mesh_selection",
        "set_object_visibility",
        "convert_to_mesh",
        "separate_loose_parts",
        "unwrap_mesh",
        "smart_project",
        # architectural / MEP systems (addon-side; no MCP tool yet)
        "build_room_shell",
        "build_wall_segment",
        "build_wall_with_door",
        "build_column",
        "set_view",
        "build_pipe_run",
        "build_cable_tray",
        "add_tray_support",
        # animation
        "set_keyframe",
        "get_keyframes",
        "set_timeline_range",
        "play_animation",
        # rendering
        "configure_render_settings",
        "render_frame",
        "render_animation",
        "generate_views",
        # materials
        "create_material",
        "set_material_properties",
        "assign_material",
        "add_shader_node",
        "connect_shader_nodes",
        "assign_builtin_texture",
        "assign_texture_map",
        # camera / light
        "create_camera",
        "set_active_camera",
        "camera_look_at",
        "create_light",
        "configure_light",
        "set_world_background",
        # print preparation / interchange
        "set_scene_units",
        "check_mesh_for_printing",
        "repair_mesh",
        "apply_voxel_remesh",
        "export_model",
        "import_model",
        "export_fbx",
        "export_gltf",
        # sculpting assists
        "enter_sculpt_mode",
        "exit_sculpt_mode",
        "set_dyntopo",
        "apply_sculpt_smooth",
        "sculpt_inflate",
        "sculpt_grab",
        "symmetrize_mesh",
        "clear_sculpt_mask",
        "invert_sculpt_mask",
        # history
        "undo",
        "redo",
    }
)

# Mirrors blender_mcp_addon/lifecycle.py READ_ONLY_COMMANDS. The mutation rule
# below must stay in sync with MutationLifecycleManager.is_mutation: a command
# is a mutation unless it reads only (get_* prefix or explicit read-only set).
READ_ONLY_OPS: frozenset[str] = frozenset(
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


def is_mutation_op(op: str) -> bool:
    """True when an addon command may mutate Blender state (needs op_id care)."""
    if not op or op.startswith("get_"):
        return False
    return op not in READ_ONLY_OPS


MAX_REQUEST_BYTES = 1024 * 1024
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
DEFAULT_TIMEOUT_MS = int(BLENDER_TRANSPORT_TIMEOUT_SECONDS * 1000)
MAX_TIMEOUT_MS = int(BLENDER_TRANSPORT_TIMEOUT_SECONDS * 1000)
MIN_TIMEOUT_MS = 100


class RuntimeTransportError(Exception):
    """Base class for typed runtime-boundary failures."""


class RuntimeUnavailableError(RuntimeTransportError):
    """Runtime endpoint unreachable before dispatch — safe to report, never a success."""


class RuntimeAuthError(RuntimeTransportError):
    """Missing/rejected runtime credential. Not retryable without operator action."""


class RuntimeGenerationMismatchError(RuntimeTransportError):
    """Stale runtime generation — result discarded before CAD effect is assumed."""


class RuntimeUncertainError(RuntimeTransportError):
    """Timeout/disconnect after dispatch started — completion unknown, no blind replay."""


class RuntimeOpRefusedError(ValueError):
    """Unknown/refused op rejected before dispatch — no CAD effect, safe to surface."""


def check_op(op: str) -> str:
    """Validate an op name against the allowlist before any dispatch."""
    name = str(op or "").strip()
    if name not in ALLOWED_OPS:
        raise RuntimeOpRefusedError(f"runtime op refused (not in allowlist): {name!r}")
    return name


def check_timeout_ms(timeout_ms: int | None) -> int:
    """Bound a dispatch deadline; violations fail before dispatch."""
    value = DEFAULT_TIMEOUT_MS if timeout_ms is None else int(timeout_ms)
    if not MIN_TIMEOUT_MS <= value <= MAX_TIMEOUT_MS:
        raise ValueError(
            f"timeout_ms must be within [{MIN_TIMEOUT_MS}, {MAX_TIMEOUT_MS}], got {value}"
        )
    return value


def check_request_size(payload: dict[str, Any]) -> dict[str, Any]:
    """Bound request bytes before dispatch."""
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    if len(raw) > MAX_REQUEST_BYTES:
        raise RuntimeOpRefusedError(
            f"runtime request oversized: {len(raw)} bytes > {MAX_REQUEST_BYTES}"
        )
    return payload


@dataclass(frozen=True)
class RuntimeRequest:
    op: str
    params: dict[str, Any] = field(default_factory=dict)
    rid: str = "unknown"
    timeout_ms: int = DEFAULT_TIMEOUT_MS
    op_id: str | None = None
    expected_generation: str | None = None
    request_id: str = field(default_factory=lambda: uuid4().hex)

    def to_wire(self) -> dict[str, Any]:
        return check_request_size(
            {
                "request_id": self.request_id,
                "op": check_op(self.op),
                "params": dict(self.params or {}),
                "rid": self.rid,
                "timeout_ms": check_timeout_ms(self.timeout_ms),
                "op_id": self.op_id,
                "expected_generation": self.expected_generation,
            }
        )


@dataclass(frozen=True)
class RuntimeResponse:
    ok: bool
    result: Any = None
    error_code: str = "ok"
    error_message: str = ""
    generation: str = "unbound"
    completion_unknown: bool = False

    @classmethod
    def from_wire(cls, payload: dict[str, Any]) -> RuntimeResponse:
        if not isinstance(payload, dict):
            raise RuntimeTransportError("malformed runtime response (not an object)")
        required_types = {
            "ok": bool,
            "error_code": str,
            "error_message": str,
            "generation": str,
            "completion_unknown": bool,
        }
        if any(type(payload.get(key)) is not kind for key, kind in required_types.items()):
            raise RuntimeTransportError("malformed runtime response field types")
        ok = payload["ok"]
        code = payload["error_code"]
        generation = payload["generation"]
        unknown = payload["completion_unknown"]
        if not code or not generation.strip() or generation == "unbound":
            raise RuntimeTransportError("runtime response lacks a bound identity or error code")
        if ok and (code != "ok" or unknown or not isinstance(payload.get("result"), dict)):
            raise RuntimeTransportError("contradictory or malformed runtime success")
        if not ok and code == "ok":
            raise RuntimeTransportError("contradictory runtime failure")
        return cls(
            ok=ok,
            result=payload.get("result"),
            error_code=code,
            error_message=payload["error_message"],
            generation=generation,
            completion_unknown=unknown,
        )


def raise_for_response(op: str, response: RuntimeResponse) -> Any:
    """Convert a verified wire response into a result or a typed error."""
    if response.completion_unknown:
        raise RuntimeUncertainError(
            response.error_message or f"runtime op {op!r} completion is unknown"
        )
    if response.ok:
        return response.result
    code = response.error_code
    message = response.error_message or f"runtime op {op!r} failed: {code}"
    if code in {"unauthorized", "forbidden"}:
        raise RuntimeAuthError(message)
    if code in {"generation_mismatch", "stale_generation"}:
        raise RuntimeGenerationMismatchError(message)
    if code in {"unknown_op", "op_refused", "oversized", "bad_request", "not_found"}:
        raise RuntimeOpRefusedError(message)
    if code in {"dispatch_timeout_uncertain", "uncertain"} or response.completion_unknown:
        raise RuntimeUncertainError(message)
    if code == "unavailable":
        raise RuntimeUnavailableError(message)
    raise RuntimeUncertainError(
        f"{message} [{code}]; completion is unknown, reconcile before retry"
    )


class BlenderRuntimeTransport(ABC):
    """Typed provider -> runtime boundary. One op call, one verified result."""

    @abstractmethod
    def call(
        self,
        op: str,
        params: dict[str, Any] | None = None,
        *,
        rid: str = "unknown",
        timeout_seconds: float | None = None,
        op_id: str | None = None,
        expected_generation: str | None = None,
    ) -> dict[str, Any]: ...

    @abstractmethod
    def health(self) -> dict[str, Any]: ...

    @abstractmethod
    def close(self) -> None: ...


class LocalBlenderRuntimeTransport(BlenderRuntimeTransport):
    """In-process delegate over a B1 BlenderRuntimePort. Default single-host path.

    No serialization boundary and no allowlist re-validation: args pass
    through unchanged and unknown commands keep the addon's own typed
    rejection, so local behavior is identical to the direct provider path.
    Timeouts reported by the addon keep their typed dict shapes
    (timeout_uncertain / expired_pending); only a pinned-generation mismatch
    raises, and the provider never pins one on this path.
    """

    def __init__(self, runtime: Any, *, generation: str = "local") -> None:
        from .runtime_port import BlenderRuntimePort

        if not isinstance(runtime, BlenderRuntimePort):
            raise TypeError("LocalBlenderRuntimeTransport requires a BlenderRuntimePort")
        self._runtime = runtime
        self._generation = str(generation or "local")
        self._closed = False

    @property
    def generation(self) -> str:
        return self._generation

    def call(
        self,
        op: str,
        params: dict[str, Any] | None = None,
        *,
        rid: str = "unknown",
        timeout_seconds: float | None = None,
        op_id: str | None = None,
        expected_generation: str | None = None,
    ) -> dict[str, Any]:
        if self._closed:
            raise RuntimeUnavailableError("local runtime transport is closed")
        if expected_generation is not None and expected_generation != self._generation:
            raise RuntimeGenerationMismatchError(
                f"runtime generation mismatch: expected {expected_generation!r}, "
                f"local generation is {self._generation!r}; result discarded"
            )
        kwargs: dict[str, Any] = {"rid": rid, "op_id": op_id}
        if timeout_seconds is not None:
            kwargs["timeout_seconds"] = timeout_seconds
        return self._runtime.execute(str(op), params, **kwargs)

    def health(self) -> dict[str, Any]:
        if self._closed:
            raise RuntimeUnavailableError("local runtime transport is closed")
        return {
            "transport": "local",
            "reachable": True,
            "generation": self._generation,
            "runtime": self._runtime.health(),
        }

    def close(self) -> None:
        self._closed = True


def _require_loopback(url: str, *, allow_remote: bool = False) -> str:
    host = (urlparse(url).hostname or "").lower()
    if host not in _LOOPBACK_HOSTS and not allow_remote:
        raise RuntimeOpRefusedError(
            f"refusing non-loopback runtime endpoint {host!r}; "
            "split-host deploy is out of scope for B2"
        )
    return url.rstrip("/")


def _no_proxy_opener() -> urllib.request.OpenerDirector:
    # Loopback runtime traffic must never leave the host via an env proxy.
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _preflight_connect(host: str, port: int, timeout_s: float) -> str:
    """One-shot TCP probe before dispatch: refused proves nothing is listening.

    Returns "open" (listener present), "refused" (nothing listening — dispatch
    is provably impossible), or "filtered" (no answer — POST decides; any
    post-connect loss stays completion-unknown).
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(max(0.2, min(2.0, timeout_s)))
    try:
        sock.connect((host, port))
        return "open"
    except ConnectionRefusedError:
        return "refused"
    except OSError:
        return "filtered"
    finally:
        try:
            sock.close()
        except OSError:
            pass


def _endpoint_host_port(base_url: str) -> tuple[str, int]:
    parts = urlparse(base_url)
    return (parts.hostname or "127.0.0.1", int(parts.port or 80))


def _post_json(
    url: str,
    payload: dict[str, Any],
    *,
    token: str,
    timeout_s: float,
) -> tuple[int, bytes]:
    """Blocking HTTP POST (no new dependencies)."""
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=raw,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Content-Length": str(len(raw)),
            "Authorization": f"Bearer {token}",
        },
    )
    try:
        with _no_proxy_opener().open(request, timeout=timeout_s) as response:
            return int(response.status or 200), response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        return int(exc.code or 500), exc.read(MAX_RESPONSE_BYTES + 1)


def _get_json(url: str, *, token: str, timeout_s: float) -> tuple[int, bytes]:
    request = urllib.request.Request(
        url, method="GET", headers={"Authorization": f"Bearer {token}"}
    )
    try:
        with _no_proxy_opener().open(request, timeout=timeout_s) as response:
            return int(response.status or 200), response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        return int(exc.code or 500), exc.read(MAX_RESPONSE_BYTES + 1)


def _decode_response(status: int, raw: bytes, *, op: str) -> RuntimeResponse:
    if len(raw) > MAX_RESPONSE_BYTES:
        raise RuntimeUncertainError(
            f"runtime response oversized ({len(raw)} bytes); discarded without trust"
        )
    if status in (401, 403):
        raise RuntimeAuthError(
            f"runtime endpoint rejected credentials for op {op!r} (http {status})"
        )
    if status == 404:
        raise RuntimeUnavailableError(f"runtime endpoint has no route for op {op!r}")
    if status >= 500:
        # 5xx after dispatch may mean Blender work started server-side: uncertain.
        raise RuntimeUncertainError(
            f"runtime endpoint error {status} for op {op!r} after dispatch; "
            "completion is unknown, blind retry is forbidden"
        )
    if status >= 400:
        raise RuntimeTransportError(f"runtime endpoint http {status} for op {op!r}")
    try:
        payload = json.loads(raw.decode("utf-8") or "{}")
        return RuntimeResponse.from_wire(payload)
    except (ValueError, UnicodeDecodeError, RuntimeTransportError) as exc:
        raise RuntimeUncertainError(
            f"untrusted runtime response for op {op!r} after dispatch; "
            "completion is unknown, reconcile before retry"
        ) from exc


class RemoteBlenderRuntimeTransport(BlenderRuntimeTransport):
    """Loopback HTTP client to a WorkstationBlenderRuntimeAgent (B2 split-process path).

    Proves the remote boundary on one host; split-host deploy comes later
    (non-loopback refused unless explicitly allowed). Auth is a bearer token
    compared server-side with compare_digest; never logged.

    Timeout rule: any timeout/disconnect once dispatch may have started is
    completion-unknown. Only pre-dispatch failures (unresolvable host,
    refused connection, refused op, refused deadline) are clean errors.
    """

    def __init__(
        self,
        base_url: str,
        auth_token: str,
        *,
        allow_remote: bool = False,
        default_timeout_ms: int = DEFAULT_TIMEOUT_MS,
    ) -> None:
        if not str(auth_token or "").strip():
            raise ValueError("RemoteBlenderRuntimeTransport requires a non-empty auth_token")
        self._base_url = _require_loopback(base_url, allow_remote=allow_remote)
        # Token is secret: keep it out of repr and logs.
        self._auth_token = str(auth_token)
        self._default_timeout_ms = check_timeout_ms(default_timeout_ms)
        self._closed = False

    def __repr__(self) -> str:
        return f"RemoteBlenderRuntimeTransport(base_url={self._base_url!r}, auth=<redacted>)"

    def call(
        self,
        op: str,
        params: dict[str, Any] | None = None,
        *,
        rid: str = "unknown",
        timeout_seconds: float | None = None,
        op_id: str | None = None,
        expected_generation: str | None = None,
    ) -> dict[str, Any]:
        if self._closed:
            raise RuntimeUnavailableError("remote runtime transport is closed")
        timeout_ms = (
            self._default_timeout_ms
            if timeout_seconds is None
            else check_timeout_ms(int(timeout_seconds * 1000))
        )
        request = RuntimeRequest(
            op=check_op(op),
            params=dict(params or {}),
            rid=rid,
            timeout_ms=timeout_ms,
            op_id=op_id,
            expected_generation=expected_generation,
        )
        wire = request.to_wire()  # bounds op + deadline + bytes before any I/O
        timeout_s = request.timeout_ms / 1000.0
        host, port = _endpoint_host_port(self._base_url)
        if _preflight_connect(host, port, timeout_s) == "refused":
            raise RuntimeUnavailableError(
                f"remote runtime refused connection before dispatch "
                f"for op {request.op!r}; nothing could have executed"
            )
        url = f"{self._base_url}/dispatch"
        try:
            status, raw = _post_json(url, wire, token=self._auth_token, timeout_s=timeout_s)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            reason = getattr(exc, "reason", None) or exc
            if isinstance(reason, ConnectionRefusedError) or isinstance(
                exc, ConnectionRefusedError
            ):
                raise RuntimeUnavailableError(
                    f"remote runtime refused connection before dispatch "
                    f"for op {request.op!r}: {exc}"
                ) from exc
            if isinstance(reason, OSError) and "getaddrinfo" in str(reason).lower():
                raise RuntimeUnavailableError(
                    f"remote runtime host unresolvable before dispatch for op {request.op!r}: {exc}"
                ) from exc
            # Anything else (timeout, reset, truncated body): bytes may have
            # reached the agent and Blender work may have started. Uncertain.
            raise RuntimeUncertainError(
                f"remote runtime op {request.op!r} lost response after dispatch "
                f"({exc}); completion is unknown, blind retry is forbidden"
            ) from exc
        response = _decode_response(status, raw, op=request.op)
        result = raise_for_response(request.op, response)
        if (
            request.expected_generation is not None
            and response.generation != request.expected_generation
        ):
            raise RuntimeUncertainError(
                f"runtime generation mismatch after dispatch: expected "
                f"{request.expected_generation!r}, "
                f"got {response.generation!r}; result for op {request.op!r} discarded"
            )
        if not isinstance(result, dict):
            raise RuntimeUncertainError(
                f"remote op {request.op!r} returned malformed result (not an object)"
            )
        return result

    def health(self) -> dict[str, Any]:
        if self._closed:
            raise RuntimeUnavailableError("remote runtime transport is closed")
        host, port = _endpoint_host_port(self._base_url)
        if _preflight_connect(host, port, 5.0) == "refused":
            raise RuntimeUnavailableError("remote runtime refused connection; agent is down")
        try:
            status, raw = _get_json(
                f"{self._base_url}/health", token=self._auth_token, timeout_s=5.0
            )
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise RuntimeUnavailableError(f"remote runtime health unreachable: {exc}") from exc
        response = _decode_response(status, raw, op="health")
        if not response.ok:
            raise RuntimeUnavailableError(
                f"remote runtime unhealthy: {response.error_message or response.error_code}"
            )
        result = response.result
        return result if isinstance(result, dict) else {"ok": True, "detail": result}

    def close(self) -> None:
        self._closed = True


def bearer_matches(presented: str, expected: str) -> bool:
    """Constant-time bearer comparison; empty expected never matches."""
    if not str(expected or ""):
        return False
    return hmac.compare_digest(str(presented or ""), str(expected))
