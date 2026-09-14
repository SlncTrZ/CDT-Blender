# src/connection.py

import json
import logging
import socket
import time

from .config import settings

logger = logging.getLogger("mcp_server")


class BlenderConnection:
    """Handles reliable on-demand socket communication with the Blender addon"""

    def recv_all(self, sock, deadline: float):
        """Receive one response without exceeding the caller's total deadline."""
        data = bytearray()
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                sock.settimeout(remaining)
                chunk = sock.recv(4096)
                if not chunk:  # Connection closed by server
                    break
                data.extend(chunk)
            except TimeoutError:
                break
            except Exception:
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

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout_seconds)
            sock.connect((settings.addon_host, settings.addon_port))

            payload = {"type": command_type, "params": clean_params, "request_id": rid}
            sock.sendall(json.dumps(payload).encode("utf-8"))

            response_data = self.recv_all(sock, deadline)
            if not response_data:
                return {"status": "error", "message": "No response from Blender"}

            return json.loads(response_data.decode("utf-8"))
        except Exception as e:
            logger.error(f"[Blender] Connection/Execution Error: {e}")
            return {"status": "error", "message": str(e)}
        finally:
            if "sock" in locals():
                try:
                    sock.close()
                except Exception:
                    pass


blender = BlenderConnection()
