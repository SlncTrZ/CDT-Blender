# blender_mcp_bridge/server.py

import contextvars
import json
import logging
import os
import random
import string
from contextlib import asynccontextmanager

import mcp.types as types
from mcp.server import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import Response
from starlette.routing import Mount, Route

from .auth import auth_failure_status, verify_token
from .config import settings
from .connection import blender, logger
from .sessions import SessionRecorder
from .tools import get_mcp_tools
from .tools.design_rules import DESIGN_RULE_HANDLERS
from .tools.provider import PROVIDER_HANDLERS

# Lifecycle / Recording State
recorder: SessionRecorder | None = None

# Transport tracking
transport_var = contextvars.ContextVar("transport", default="MCP")

# Suppress noise from SDK and Starlette
logging.getLogger("mcp").setLevel(logging.WARNING)
logging.getLogger("starlette").setLevel(logging.WARNING)

# Initialize MCP Server
mcp_server = Server("blender-mcp-bridge")

ASSETS_DIR = settings.assets_dir


class PathContainmentError(ValueError):
    """A file argument points outside BLENDER_ALLOW_ROOTS. Fail closed."""


def _allow_roots() -> list[str]:
    roots = settings.allow_roots or ([ASSETS_DIR] if ASSETS_DIR else [os.getcwd()])
    return [os.path.normcase(os.path.abspath(root)) for root in roots]


def _contained(path: str) -> bool:
    needle = os.path.normcase(os.path.abspath(path))
    return any(needle == root or needle.startswith(root + os.sep) for root in _allow_roots())


def resolve_path(args):
    """Resolve relative paths against ASSETS_DIR and contain them in allow-roots.

    CDT fork: absolute paths no longer pass through unchecked. Anything
    outside BLENDER_ALLOW_ROOTS raises PathContainmentError before Blender
    is contacted.
    """
    base = ASSETS_DIR or os.getcwd()

    for key in ["image_path", "filepath"]:
        if (
            key in args
            and args[key]
            and isinstance(args[key], str)
            and not os.path.isabs(args[key])
        ):
            base_path = os.path.join(base, args[key])
            resolved_path = base_path
            # print(f"[DEBUG] Checking base path: {base_path}")

            # If the exact file exists, use it
            if os.path.exists(base_path):
                # print(f"[DEBUG] Found exact match: {base_path}")
                resolved_path = base_path
            else:
                # Try extensions
                # print("Exact match failed. Trying extensions...")
                # Split off any existing extension to try others
                root, _ = os.path.splitext(base_path)

                for ext in [".exr", ".hdr", ".png", ".jpg", ".jpeg", ".tiff", ".tga"]:
                    test_path = root + ext
                    # print(f"[DEBUG] Checking Extension: {test_path}")
                    if os.path.exists(test_path):
                        # print(f"[DEBUG] Found match with extension: {test_path}")
                        resolved_path = test_path
                        break

            # Normalize path for cross-platform compatibility
            args[key] = os.path.normpath(resolved_path).replace("\\", "/")
            # print(f"[DEBUG] Final resolved path: {args[key]}")

    # CDT fork: contain every file argument (resolved or absolute) inside
    # the allow-roots. Absolute paths used to pass through unchecked.
    for key in ["image_path", "filepath"]:
        value = args.get(key)
        if value and isinstance(value, str) and not _contained(value):
            raise PathContainmentError(
                f"'{key}' points outside BLENDER_ALLOW_ROOTS "
                f"({os.pathsep.join(_allow_roots())}): {value}"
            )
    return args


@mcp_server.list_tools()
async def list_tools() -> list[types.Tool]:
    """Expose available Blender tools to the AI Agent"""
    return get_mcp_tools()


def _answer_locally(name: str, clean_args: dict) -> dict | None:
    """Answer read-only local tools (design rules, provider contract).

    Returns the result dict, or None when the tool must go to Blender.
    Design-rule lookups and SlncTrZ provider tools short-circuit here:
    Blender has no handler for them, they never mutate state, and recording
    them would put noise into a replayable session.
    """
    if name in DESIGN_RULE_HANDLERS:
        return DESIGN_RULE_HANDLERS[name](clean_args)
    if name in PROVIDER_HANDLERS:
        return PROVIDER_HANDLERS[name](clean_args)
    return None


@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Handle tool calls from the AI Agent"""
    rid = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    transport = transport_var.get()

    # Strip n8n-specific metadata
    meta = {"sessionId", "action", "chatInput", "toolCallId", "id"}
    clean_args = {k: v for k, v in arguments.items() if k not in meta}

    # Resolve + contain paths (fail closed before Blender is contacted)
    try:
        clean_args = resolve_path(clean_args)
    except PathContainmentError as exc:
        logger.warning(f"[{transport}] [{rid}] validation_error: {exc}")
        return [
            types.TextContent(
                type="text",
                text=json.dumps(
                    {
                        "kind": "validation_error",
                        "retryable": False,
                        "message": str(exc),
                    }
                ),
            )
        ]

    if name in {"document_open", "document_save", "document_save_as"}:
        clean_args["_allow_roots"] = _allow_roots()

    logger.info(f"[{transport}] [{rid}] Tool Call: {name} with params: {clean_args}")

    local_result = _answer_locally(name, clean_args)
    if local_result is not None:
        status = "ERROR" if local_result.get("status") == "error" else "OK"
        logger.info(f"[{transport}] [{rid}] {status}: {name} (answered locally)")
        return [types.TextContent(type="text", text=json.dumps(local_result, indent=2))]

    if recorder:
        recorder.record_command(name, clean_args)

    blender_res = blender.send_command(name, clean_args, rid)
    log_status, log_msg, blender_res = _normalize_result(name, blender_res)

    logger.info(f"[{transport}] [{rid}] [{log_status}] {log_msg}")

    return [types.TextContent(type="text", text=json.dumps(blender_res, indent=2))]


def _normalize_result(name: str, blender_res):
    """Flatten nested bridge results and derive the console log line.

    Returns (log_status, log_msg, normalized_result). Pure reshaping —
    no Blender contact, no policy decisions.
    """
    # Flatten nested results from bridge
    if isinstance(blender_res, dict) and "result" in blender_res and "status" in blender_res:
        status_val = blender_res["status"]
        blender_res = blender_res["result"]
        if isinstance(blender_res, dict) and "status" not in blender_res:
            blender_res["status"] = status_val

    # Guard: tool returned None (missing return statement) — convert to a safe dict
    if blender_res is None:
        blender_res = {
            "status": "success",
            "message": f"{name} completed (no result returned).",
        }

    # Add success indicator to the message
    log_status = "OK"
    if isinstance(blender_res, dict):
        if (
            "message" not in blender_res
            and "status" in blender_res
            and (blender_res["status"] == "success" or blender_res.get("success") is True)
        ):
            blender_res["message"] = f"{name} completed successfully."

        if "error" in blender_res or blender_res.get("status") == "error":
            log_status = "ERROR"

    # Mirror success indicator in local console log
    if isinstance(blender_res, dict):
        log_msg = blender_res.get("message", blender_res.get("status", "Done"))
        if "error" in blender_res:
            log_msg = f"ERROR: {blender_res['error']}"
    else:
        log_msg = str(blender_res)

    return log_status, log_msg, blender_res


# MCP Application Logic (Streamable Transport)
# Lines below set up the Starlette/MCP integration
session_manager = StreamableHTTPSessionManager(app=mcp_server, json_response=True, stateless=True)


@asynccontextmanager
async def lifespan(app: Starlette):
    """Manage the lifecycle of the MCP session manager"""
    # print("[DEBUG] Starlette lifespan starting...")
    async with session_manager.run():
        # print("[DEBUG] MCP Session Manager active.")
        yield
    # print("[DEBUG] Starlette lifespan shutting down...")


async def _auth_rejection(scope, receive, send, reason: str):
    """Fail-closed 401/403 for /mcp. Never logs or echoes the credential."""
    body = json.dumps(
        {
            "error": {
                "kind": "authorization_error" if reason == "forbidden" else "authentication_error",
                "retryable": False,
                "message": (
                    "Valid identity but denied."
                    if reason == "forbidden"
                    else "Missing or invalid credentials. Send Authorization: Bearer "
                    "<token> or X-API-Key: <token>."
                ),
            }
        }
    ).encode("utf-8")
    response = Response(
        content=body,
        status_code=auth_failure_status(reason),
        media_type="application/json",
    )
    await response(scope, receive, send)


async def mcp_asgi(scope, receive, send):
    """Raw ASGI bridge to MCP session manager. Handles OPTIONS for CORS preflight."""
    if scope["type"] == "http":
        path = scope.get("path", "")
        if path.startswith("/mcp"):
            raw_headers = scope.get("headers", [])
            headers = {k.decode("latin-1"): v.decode("latin-1") for k, v in raw_headers}
            ok, reason = verify_token(headers)
            if not ok:
                logger.warning(f"[auth] rejected {scope.get('method')} {path} (reason: {reason})")
                await _auth_rejection(scope, receive, send, reason)
                return
        method = scope.get("method")
        # logger.info(f"[ASGI] {method} path='{path}'")

        if method == "OPTIONS":
            # Return 200 for CORS preflight — middleware will add the headers
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b""})
            return

        # Detect transport type
        path = scope.get("path", "")
        method = scope.get("method", "POST")
        headers = scope.get("headers", [])
        query = scope.get("query_string", b"").decode("utf-8")

        # 1. Check for Explicit Marking
        explicit_stateless = any(h[0] == b"x-mcp-model" and h[1] == b"stateless" for h in headers)
        explicit_stateful = "transport=stateful" in query

        # 2. Heuristic fallback
        is_handshake = method == "GET" and any(
            h[0] == b"accept" and b"text/event-stream" in h[1] for h in headers
        )
        is_stateful_heuristic = is_handshake or "session_id=" in query

        # Final decision
        if explicit_stateful:
            res = "Stateful"
        elif explicit_stateless:
            res = "Stateless"
        else:
            # Fallback to path logic
            is_root = path in ("/", "", "/mcp", "/mcp/")
            res = "Stateful" if (is_stateful_heuristic or not is_root) else "Stateless"

        transport_var.set(res)

    await session_manager.handle_request(scope, receive, send)


async def root_redirect(request):
    return Response(
        "CDT-Blender provider (blender) is running. Call the help tool first.",
        media_type="text/plain",
    )


async def healthz(request):
    """Unauthenticated liveness probe — never a business operation."""
    from starlette.responses import JSONResponse

    from . import provider_contract as contract

    return JSONResponse(
        {
            "status": "ok",
            "provider": contract.PROVIDER_ID,
            "provider_version": contract.PROVIDER_VERSION,
            "contract_version": contract.CONTRACT_VERSION,
        }
    )


# Create the Starlette app.
# CDT fork: provider-only surface. The upstream Studio UI, rendered-view and
# model static mounts, and the in-provider LLM assistant endpoints are out
# of the provider contract and stay out.
starlette_app = Starlette(
    routes=[
        Route("/", root_redirect),
        Route("/healthz", healthz, methods=["GET"]),
        Mount("/mcp", app=mcp_asgi),
    ],
    lifespan=lifespan,
)

# Add CORS middleware
starlette_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Replace the mcp_app with starlette_app for the final entry point
# Note: Keep variable name as 'app' for uvicorn compatibility in main.py
app = starlette_app
