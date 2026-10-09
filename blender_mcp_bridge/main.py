# blender_mcp_bridge/main.py

import asyncio
import logging
import threading

import click
import uvicorn

from .config import settings
from .sessions import BridgeSession, SessionMetadata, SessionPlayer, SessionRecorder

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("mcp_server")


def _blender_health_check(interval: int = 5):
    """Log configured native reachability without probing the wrong host."""
    from .runtime_factory import get_runtime

    was_connected = None
    while True:
        connected = get_runtime().port.status()["addon"].get("connected") is True
        if connected != was_connected:
            logger.info("Blender addon connected=%s", connected)
            was_connected = connected
        threading.Event().wait(interval)


async def _serve_stdio():
    import anyio
    from mcp import types
    from mcp.server.stdio import stdio_server
    from mcp.shared.message import SessionMessage

    from .server import mcp_server

    async with stdio_server() as (reader, writer):
        forward_writer, forward_reader = anyio.create_memory_object_stream[
            SessionMessage | Exception
        ](0)

        async def forward_requests():
            async with forward_writer:
                async for item in reader:
                    root = item.message.root if isinstance(item, SessionMessage) else None
                    if isinstance(root, types.JSONRPCRequest) and root.method == "server/discover":
                        # This SDK serves MCP v1. Refuse modern discovery with the
                        # JSON-RPC method code so clients can negotiate legacy MCP.
                        await writer.send(
                            SessionMessage(
                                types.JSONRPCMessage(
                                    types.JSONRPCError(
                                        jsonrpc="2.0",
                                        id=root.id,
                                        error=types.ErrorData(
                                            code=-32601, message="Method not found"
                                        ),
                                    )
                                )
                            )
                        )
                    else:
                        await forward_writer.send(item)

        async with forward_reader, anyio.create_task_group() as tasks:
            tasks.start_soon(forward_requests)
            await mcp_server.run(forward_reader, writer, mcp_server.create_initialization_options())


@click.group()
def cli():
    """Blender MCP Bridge CLI"""
    pass


@cli.command()
@click.option("--transport", type=click.Choice(["http", "stdio"]), default="http")
@click.option("--host", default=settings.bridge_host, help="Host to bind the server to")
@click.option("--port", default=settings.bridge_port, help="Port to bind the server to")
@click.option(
    "--record",
    "record_path",
    type=click.Path(),
    help="Path to record the session to (JSON)",
)
@click.option("--name", default="Recorded Session", help="Session name")
@click.option("--model", default="", help="AI model name used")
@click.option("--description", default="", help="Session description")
@click.option("--url", "doc_url", default="", help="Documentation URL")
def serve(transport, host, port, record_path, name, model, description, doc_url):
    """Start the Blender MCP server"""
    import os

    import blender_mcp_bridge.server as server_mod

    settings.mcp_transport = transport
    from .runtime_factory import get_runtime

    try:
        get_runtime()
    except (ValueError, OSError) as exc:
        raise click.ClickException(
            "Invalid runtime profile; check binding and credential channel"
        ) from exc
    if transport == "stdio":
        if record_path:
            raise click.ClickException("Session recording is unavailable on stdio")
        asyncio.run(_serve_stdio())
        return

    # CDT fork: fail closed. Network transport without BLENDER_MCP_TOKEN is
    # refused unless MCP_ALLOW_UNAUTHENTICATED=1 (strictly local loopback testing only).
    # H13: Unauthenticated mode is strictly forbidden on non-loopback interfaces!
    token = os.getenv("BLENDER_MCP_TOKEN", "").strip()
    is_loopback = host in ("127.0.0.1", "localhost", "::1")
    if not token:
        if os.getenv("MCP_ALLOW_UNAUTHENTICATED") == "1":
            if not is_loopback:
                raise click.ClickException(
                    f"Refusing unauthenticated serve on non-loopback interface '{host}'. "
                    "MCP_ALLOW_UNAUTHENTICATED=1 is strictly permitted on loopback (127.0.0.1 / localhost) only."
                )
        else:
            raise click.ClickException(
                "Refusing to serve without BLENDER_MCP_TOKEN. Set BLENDER_MCP_TOKEN "
                "(recommended) or MCP_ALLOW_UNAUTHENTICATED=1 for local loopback testing only."
            )

    if record_path:
        metadata = SessionMetadata(
            name=name, model=model, description=description, documentation_url=doc_url
        )
        server_mod.recorder = SessionRecorder(record_path, metadata)
        print(f"RECORDER ACTIVE: Saving to {record_path}")

    print("============================================================")
    print("Starting Blender MCP Bridge Server")
    print(f"HTTP Streamable: http://{host}:{port}/mcp")
    print("============================================================")

    # Start Blender addon health check in background
    t = threading.Thread(
        target=_blender_health_check,
        daemon=True,
    )
    t.start()

    # server_mod.app is a real ASGI3 app at runtime, but uvicorn types this
    # parameter with asgiref's ASGI3Application (strict TypedDict scopes) while
    # Starlette annotates __call__ with its own looser aliases
    # (Scope = MutableMapping[str, Any]). The two never unify structurally, so
    # Pylance reports a false positive here. mypy — what CI actually runs —
    # accepts it. Narrowly scoped to this call rather than silenced globally.
    uvicorn.run(  # pyright: ignore[reportArgumentType]
        server_mod.app, host=host, port=port, log_level="warning", access_log=False
    )


@cli.command()
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--transport",
    type=click.Choice(["stateless", "stateful"]),
    default="stateful",
    help="Transport mode to use",
)
@click.option("--host", default=settings.bridge_url, help="Target MCP Server URL")
@click.option(
    "--branch",
    "branch",
    default=None,
    help="Play only this branch's command ranges. If the session defines branches "
    "and this is omitted, the first branch is played automatically.",
)
@click.option(
    "--param",
    "param",
    multiple=True,
    metavar="NAME=VALUE",
    help="Override a session parameter (repeatable). Any parameter not overridden "
    "uses the session's own default from its 'parameters' block.",
)
def play(path, transport, host, branch, param):
    """Playback a recorded session JSON file"""
    print(f"Playing back session from {path}...")
    session = BridgeSession.load(path)
    player = SessionPlayer(transport=transport, host=host)

    params = {}
    for entry in param:
        if "=" not in entry:
            raise click.BadParameter(f"expected NAME=VALUE, got '{entry}'", param_hint="--param")
        name, value = entry.split("=", 1)
        params[name] = value

    # Fail before opening a connection: a misspelled --param would otherwise be
    # ignored, and playback would report 100% success while quietly building
    # the session's default geometry.
    if session.parameters:
        unknown = sorted(set(params) - set(session.parameters))
        if unknown:
            import difflib

            lines = []
            for name in unknown:
                near = difflib.get_close_matches(name, session.parameters, n=3, cutoff=0.7)
                hint = f"  did you mean: {', '.join(near)}?" if near else ""
                lines.append(f"  ✗ {name}={params[name]}{hint}")
            known = "\n".join(f"    {n} = {v}" for n, v in sorted(session.parameters.items()))
            raise click.BadParameter(
                "unknown parameter(s) —\n\n"
                + "\n".join(lines)
                + f"\n\n  This session accepts:\n{known}",
                param_hint="--param",
            )

    successes, failures = asyncio.run(player.play(session, branch=branch, params=params))
    if failures > 0:
        raise click.ClickException(f"Playback encountered {failures} error(s).")


if __name__ == "__main__":
    cli()
