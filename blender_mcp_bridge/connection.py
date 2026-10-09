# src/connection.py

import json
import logging
import socket
import time

from .config import settings

logger = logging.getLogger("mcp_server")

MAX_REQUEST_BYTES = 1024 * 1024
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
SOCKET_CHUNK_BYTES = 4096

# Bridge transport deadline. Must stay ABOVE the addon COMMAND_WAIT_TIMEOUT
# (60s) so the addon's typed timeout/error arrives instead of being masked as
# a transport timeout. Neither timeout cancels Blender-side work — a timeout is
# NOT proof of cancellation; re-query state before retrying a mutation.
BLENDER_TRANSPORT_TIMEOUT_SECONDS = 120.0


def _connection_error(kind, message, *, retryable=False):
    return {
        "status": "error",
        "kind": kind,
        "retryable": retryable,
        "message": message,
    }


def _uncertain_response(op_id):
    result = _connection_error(
        "timeout_uncertain",
        "Blender response lost or invalid after dispatch; completion is unknown. "
        "Call reconcile_operation with this op_id before retrying.",
        retryable=True,
    )
    result["op_id"] = op_id
    return result


class BlenderConnection:
    """Handles reliable on-demand socket communication with the Blender addon"""

    def recv_all(self, sock, deadline: float, max_bytes: int = MAX_RESPONSE_BYTES):
        """Receive one response under a total deadline and byte budget."""
        data = bytearray()
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                sock.settimeout(remaining)
                chunk = sock.recv(SOCKET_CHUNK_BYTES)
                if not chunk:  # Connection closed by server
                    break
                data.extend(chunk)
                if len(data) > max_bytes:
                    raise ValueError("Response exceeds transport byte budget.")
            except TimeoutError:
                break
        return bytes(data)

    def send_command(
        self,
        command_type,
        params=None,
        rid="unknown",
        timeout_seconds: float = BLENDER_TRANSPORT_TIMEOUT_SECONDS,
        op_id: str | None = None,
    ):
        """Send a command to Blender under one bounded connect/receive deadline."""
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

        clean_params = params if params else {}
        deadline = time.monotonic() + timeout_seconds
        payload = {
            "type": command_type,
            "params": clean_params,
            "request_id": rid,
            "op_id": op_id or rid,
        }
        request_data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        if len(request_data) > MAX_REQUEST_BYTES:
            return _connection_error(
                "validation_error",
                "Request exceeds transport byte budget.",
            )

        sock = None
        dispatched = False
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return _connection_error(
                    "timeout",
                    "Transport deadline exceeded before connecting to Blender.",
                    retryable=True,
                )
            sock.settimeout(remaining)
            sock.connect((settings.addon_host, settings.addon_port))
            dispatched = True  # sendall may fail after a partial write.
            sock.sendall(request_data)

            response_data = self.recv_all(sock, deadline, max_bytes=MAX_RESPONSE_BYTES)
            if not response_data:
                return _uncertain_response(payload["op_id"])

            try:
                response = json.loads(response_data.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return _uncertain_response(payload["op_id"])
            if not isinstance(response, dict) or response.get("status") not in {"success", "error"}:
                return _uncertain_response(payload["op_id"])
            return response
        except Exception as e:
            logger.error(f"[Blender] Connection/Execution Error: {e}")
            if dispatched:
                return _uncertain_response(payload["op_id"])
            return _connection_error(
                "provider_unavailable",
                "Blender addon transport is unavailable.",
                retryable=True,
            )
        finally:
            if sock is not None:
                try:
                    sock.close()
                except Exception:
                    pass


blender = BlenderConnection()
