"""One process-wide runtime selection for dispatch, status and capabilities."""

from __future__ import annotations

import os
from dataclasses import dataclass

from .config import Config, settings
from .local_runtime import LocalBlenderRuntimeAdapter
from .path_policy import RuntimePathPolicy
from .remote_runtime import RemoteBlenderRuntimeAdapter
from .runtime_port import BlenderRuntimePort
from .runtime_transport import (
    BlenderRuntimeTransport,
    LocalBlenderRuntimeTransport,
    RemoteBlenderRuntimeTransport,
)


@dataclass
class RuntimeBundle:
    port: BlenderRuntimePort
    transport: BlenderRuntimeTransport
    paths: RuntimePathPolicy | None = None


def _read_token(config: Config) -> str:
    """Consume an inherited descriptor once; never put credential values in config."""
    if not config.runtime_token_fd:
        raise ValueError("remote runtime requires an inherited credential descriptor")
    fd = int(config.runtime_token_fd)
    with os.fdopen(fd, "rb", closefd=True) as stream:
        data = stream.read(4097)
    if not data or len(data) > 4096:
        raise ValueError("runtime credential must be within 1..4096 bytes")
    token = data.decode("utf-8").strip()
    if not token:
        raise ValueError("runtime credential is empty")
    return token


def create_runtime(config: Config) -> RuntimeBundle:
    if config.runtime_mode == "local":
        port = LocalBlenderRuntimeAdapter()
        return RuntimeBundle(port, LocalBlenderRuntimeTransport(port))
    if config.runtime_mode != "remote":
        raise ValueError("BLENDER_RUNTIME_MODE must be local or remote")
    if not config.runtime_generation:
        raise ValueError("remote runtime requires an explicitly pinned generation")
    paths = RuntimePathPolicy(config.runtime_platform, config.assets_dir or "", config.allow_roots)
    transport = RemoteBlenderRuntimeTransport(
        config.runtime_url, _read_token(config), expected_generation=config.runtime_generation
    )
    remote = RemoteBlenderRuntimeAdapter(transport, expected_generation=config.runtime_generation)
    return RuntimeBundle(remote, transport, paths)


_default_runtime: RuntimeBundle | None = None


def get_runtime() -> RuntimeBundle:
    global _default_runtime
    if _default_runtime is None:
        _default_runtime = create_runtime(settings)
    return _default_runtime
