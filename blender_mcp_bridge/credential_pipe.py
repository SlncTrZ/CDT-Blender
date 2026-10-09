"""Windows owner-only, local-only in-memory runtime credential handoff.

No credential files or environment values. The server retains the first pipe
instance for its lifetime. Bounded nonblocking message I/O includes an ACK so
disconnect cannot discard unread credential bytes.
"""

from __future__ import annotations

import json
import re
import threading
import time
from typing import Any

_LIMIT = 4096
_FIRST_INSTANCE = 0x00080000
_REJECT_REMOTE = 0x00000008


def _pipe_path(name: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", name):
        raise ValueError("credential pipe name must contain only letters, digits, _ or -")
    return "\\\\.\\pipe\\" + name


def _windows():
    import pywintypes
    import win32api
    import win32con
    import win32file
    import win32pipe
    import win32security

    return pywintypes, win32api, win32con, win32file, win32pipe, win32security


def _owner_security():
    pywintypes, api, con, _, _, security = _windows()
    token = security.OpenProcessToken(api.GetCurrentProcess(), con.TOKEN_QUERY)
    try:
        sid = security.GetTokenInformation(token, security.TokenUser)[0]
        owner = security.ConvertSidToStringSid(sid)
    finally:
        token.Close()
    descriptor = security.ConvertStringSecurityDescriptorToSecurityDescriptor(
        f"D:P(A;;GA;;;SY)(A;;GA;;;{owner})", security.SDDL_REVISION_1
    )
    attributes = pywintypes.SECURITY_ATTRIBUTES()
    attributes.SECURITY_DESCRIPTOR = descriptor
    attributes.bInheritHandle = False
    return attributes


def _read_message(handle: Any, deadline: float, stop: threading.Event) -> bytes:
    error, _, _, file, _, _ = _windows()
    while time.monotonic() < deadline and not stop.is_set():
        try:
            status, data = file.ReadFile(handle, _LIMIT)
            if status == 0 and data:
                return bytes(data)
        except error.error as exc:
            if exc.winerror != 232:  # ERROR_NO_DATA on a nonblocking empty pipe
                raise
        stop.wait(0.02)
    raise TimeoutError("credential channel deadline exceeded")


class CredentialBroker:
    def __init__(self, name: str, payload: dict[str, Any]) -> None:
        self._name = _pipe_path(name)
        self._payload = json.dumps(payload, separators=(",", ":")).encode()
        if len(self._payload) > _LIMIT:
            raise ValueError("credential envelope too large")
        self._stop = threading.Event()
        self._handle: Any = None
        self._thread: threading.Thread | None = None

    def __repr__(self) -> str:
        return "CredentialBroker(payload=<redacted>)"

    def start(self) -> None:
        _, _, _, _, pipe, _ = _windows()
        self._handle = pipe.CreateNamedPipe(
            self._name,
            pipe.PIPE_ACCESS_DUPLEX | _FIRST_INSTANCE,
            pipe.PIPE_TYPE_MESSAGE | pipe.PIPE_READMODE_MESSAGE | pipe.PIPE_NOWAIT | _REJECT_REMOTE,
            1,
            _LIMIT,
            _LIMIT,
            3000,
            _owner_security(),
        )
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    @property
    def alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _connect(self) -> bool:
        error, _, _, _, pipe, _ = _windows()
        try:
            pipe.ConnectNamedPipe(self._handle, None)
            return True
        except error.error as exc:
            if exc.winerror == 535:  # client already connected
                return True
            if exc.winerror == 536:  # listening without a client
                return False
            if exc.winerror == 232:
                pipe.DisconnectNamedPipe(self._handle)
                return False
            raise

    def _serve(self) -> None:
        error, _, _, file, pipe, _ = _windows()
        while not self._stop.is_set():
            if not self._connect():
                self._stop.wait(0.02)
                continue
            try:
                status, written = file.WriteFile(self._handle, self._payload)
                if status != 0 or written != len(self._payload):
                    raise OSError("credential handoff incomplete")
                acknowledgement = _read_message(self._handle, time.monotonic() + 3, self._stop)
                if acknowledgement != b"ACK":
                    raise ValueError("invalid credential channel acknowledgement")
            except (error.error, OSError, ValueError, TimeoutError):
                pass  # no payload or credential-bearing exception is logged
            finally:
                try:
                    pipe.DisconnectNamedPipe(self._handle)
                except error.error:
                    pass

    def close(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=4)
        if self._handle is not None:
            self._handle.Close()
            self._handle = None


def read_credential(name: str) -> dict[str, Any]:
    _, _, con, file, pipe, _ = _windows()
    path = _pipe_path(name)
    pipe.WaitNamedPipe(path, 3000)
    handle = file.CreateFile(
        path,
        con.GENERIC_READ | con.GENERIC_WRITE,
        0,
        None,
        con.OPEN_EXISTING,
        con.SECURITY_SQOS_PRESENT | 0x00010000,  # SECURITY_IDENTIFICATION
        None,
    )
    try:
        pipe.SetNamedPipeHandleState(
            handle, pipe.PIPE_READMODE_MESSAGE | pipe.PIPE_NOWAIT, None, None
        )
        raw = _read_message(handle, time.monotonic() + 3, threading.Event())
        payload = json.loads(raw)
        if not isinstance(payload, dict) or not all(
            isinstance(payload.get(key), str) and payload[key] for key in ("token", "generation")
        ):
            raise ValueError("invalid runtime credential envelope")
        file.WriteFile(handle, b"ACK")
        return payload
    finally:
        handle.Close()
