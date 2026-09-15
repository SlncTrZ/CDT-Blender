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


def _connection_error(kind, message, *, retryable=False):
    return {
        "status": "error",
        "kind": kind,
        "retryable": retryable,
        "message": message,
    }


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
        self, command_type, params=None, rid="unknown", timeout_seconds: float = 120.0
    ):
        """Send a command to Blender under one bounded connect/receive deadline."""
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

        clean_params = params if params else {}
        deadline = time.monotonic() + timeout_seconds
        payload = {"type": command_type, "params": clean_params, "request_id": rid}
        request_data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        if len(request_data) > MAX_REQUEST_BYTES:
            return _connection_error(
                "validation_error",
                "Request exceeds transport byte budget.",
            )

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
            sock.sendall(request_data)

            response_data = self.recv_all(sock, deadline, max_bytes=MAX_RESPONSE_BYTES)
            if not response_data:
                kind = "timeout" if time.monotonic() >= deadline else "provider_unavailable"
                return _connection_error(
                    kind,
                    "No response from Blender before the transport completed.",
                    retryable=True,
                )

            try:
                return json.loads(response_data.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return _connection_error(
                    "internal_error",
                    "Blender returned an invalid transport response.",
                )
        except ValueError as e:
            logger.error(f"[Blender] Connection/Execution Error: {e}")
            return _connection_error("internal_error", str(e))
        except Exception as e:
            logger.error(f"[Blender] Connection/Execution Error: {e}")
            return _connection_error(
                "provider_unavailable",
                "Blender addon transport is unavailable.",
                retryable=True,
            )
        finally:
            if "sock" in locals():
                try:
                    sock.close()
                except Exception:
                    pass


blender = BlenderConnection()
