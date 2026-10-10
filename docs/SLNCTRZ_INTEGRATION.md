# Gateway integration

The [runtime guide](TOOL_GUIDE.md) owns tool behavior and the contract hash.
For versioned installation, auth-safe promotion and rollback, see [Release & deployment](RELEASE_AND_DEPLOYMENT.md). Current source package `0.2.1` has contract v10/121 tools; this does **not** imply it is active on the Gateway.
The [generated reference](tools.md) lists the bridge tools.

| Item | Setting |
| --- | --- |
| Provider | `blender`; gateway namespace `blender.<tool>` |
| Endpoint | Authenticated Streamable HTTP `POST /mcp/` |
| Liveness | `GET /healthz`; does not prove native readiness |
| Credential source | `BLENDER_MCP_TOKEN` from the deployment environment/secret manager |
| Local binding | `127.0.0.1:8008`; addon socket remains workstation-local |

## Operate

1. Start Blender in the intended interactive user session, enable the addon and
   start its server.
2. Serve the bridge with deployment-managed authentication.
3. Discover status/capabilities and verify addon connection, application version,
   active object and mode before native work.
4. Pin the running contract hash; refresh help/catalog when it changes.

The measured baseline is Blender 4.5.3 LTS on Windows 11. Session-0 liveness or
background discovery does not prove interactive EDIT_MESH/SCULPT readiness.
The runtime capability map decides supported operations; do not infer support
from an upstream feature list.

## Failures and lifecycle

Authentication fails closed. Unsupported operations refuse explicitly.
A dispatch timeout or lost response can leave uncertain completion; reconcile
before retrying non-idempotent work.

Use an authenticated private transport for a remote gateway. An authorized
external controller owns application readiness, gateway activation and client
catalog refresh. Provider liveness and native readiness are separate.
Stop/drain must protect dirty documents, reconcile pending work and respect
process ownership.

See [lifecycle ownership](https://github.com/SlncTrZ/CDT_Engineer/blob/main/docs/EXECUTION_LIFECYCLE_CONTRACT.md)
and [contributor validation](../tests/README.md).
