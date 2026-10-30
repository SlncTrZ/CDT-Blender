# Gateway integration

The [runtime guide](TOOL_GUIDE.md) owns tool behavior and the contract hash.
For versioned installation, auth-safe promotion and rollback, see [Release & deployment](RELEASE_AND_DEPLOYMENT.md). Current unreleased source candidate `0.2.3` has contract v10/121 tools; this does **not** imply it is active on the Gateway.
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

## Hybrid On-Demand — P0 source candidate (not deployed)

**Policy:** Gateway and the Blender MCP bridge are control-plane services on
`.227`; the Windows agent, Blender GUI and addon on `.171` remain
execution-plane services started only on authorized demand. This source change
does not itself install, enable or remotely start any workstation application.

**Bridge identity must not depend on the workstation credential:**
`BLENDER_MCP_TOKEN` comes exclusively from an owner-managed Gateway credential
source, provisioned before the new HTTP bridge is enabled. It must be independent
of the short-lived workstation runtime token and must never be written to the
profile, a log, CLI argument or knowledge store. A missing managed MCP token
refuses HTTP startup even in standby. Unauthenticated local testing is forcibly
disabled by the new operator launcher.

**Source operator entry point:**

```bash
cdt-blender-profile serve-http \
  --profile /path/to/installed/release/profile.json --port 8812
```

The `cdt-blender-profile` CLI is included in the versioned wheel using the
same audited source as `scripts/launch_runtime_profile.py`; no source checkout
is required on the production Gateway.

This entry point validates the installed hashes and starts the HTTP bridge
even if the workstation or its credential broker is offline. It sets the
opt-in `BLENDER_RUNTIME_ON_DEMAND=1`. In standby, both
`BLENDER_RUNTIME_GENERATION` and `BLENDER_RUNTIME_TOKEN_FD` are absent;
`help`, `system_status`, `system_capabilities` and MCP discovery remain
available, while every native runtime call fails closed with
`provider_unavailable`. Partial binding (generation without credential, or
vice versa) never activates native execution.

**Release-local generation binding:** The profile's `binding_file` must
resolve to `binding.json` in the **same directory as that profile**.
Cross-release paths are refused before an operator `bind` action.
The `serve-http` entry point stays in standby if the path is stale, the
agent is unavailable, the generation changed, or authenticated heartbeat
fails. It never accepts a new generation implicitly.

**On-demand attachment sequence:**
1. The independently authorized Agent/Controller checks the requested host,
   session ownership, readiness and dirty-document policy.
2. It starts the existing Windows Task Scheduler runtime in the correct
   interactive session without enabling boot autostart. It waits for broker
   and authenticated runtime health.
3. It verifies the installed release, exact current generation and
   release-local binding, then explicitly accepts that generation via
   the `bind` operator operation. Never rebind during an uncertain mutation.
4. It restarts **only the Blender HTTP bridge**, not the whole SlncTrZ
   Gateway, to attach the verified credential through a one-time inherited
   descriptor. This P0 implementation does **not** hot-attach without a bridge
   restart. A future bounded Controller can own that transition.
5. It verifies HTTP `/healthz`, Gateway authenticated Test/Sync, the
   refreshed 121-tool catalog, provider status/capabilities and actual addon
   runtime readiness before allowing any native action. `/healthz` alone
   never proves Blender GUI/addon readiness.

**Promotion gate:** The existing Git tag `v.0.2.2` predates this P0 patch.
Do not relabel or overwrite its release artifacts: commit and qualify the P0
changes under a **new** stable package version, matching lockfile, provider
identity and addon version, with exact-source CI and native Windows qualification
before promotion.

Existing production `cdt-blender.service` on `.227`
uses its own installed launcher and credential profile. Updating source alone
does not update that service or the Gateway's credential reference. Do not
switch `ExecStart`, migrate Gateway authentication or reload/restart
production until owner-managed independent authentication has been
provisioned, current source/wheel and addon hashes are pinned and a
separate rollback-tested promotion has been authorized. Keep the old
release intact for rollback and do not touch active Blender scenes.

**Required acceptance:** Offline workstation still yields authenticated MCP
initialize and tool discovery, anonymous calls receive 401, native calls
cannot dispatch, partial/stale binding is refused, live agent generation is
verified before attach, and gateway discovery is refreshed only after
provider readiness. Treat transient startup and provider liveness as
distinct from interactive native acceptance.

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
