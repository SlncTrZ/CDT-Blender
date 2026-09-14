# SlncTrZ-MCP Integration — CDT-Blender (`blender`)

> Companion to `specs/MCP_PROVIDER_STANDARD.md` (Draft v0.2) and the runtime
> `docs/TOOL_GUIDE.md`. The `help` tool is authoritative at runtime; this
> file is the static gateway-wiring reference.

## Endpoint & auth

| Item | Value |
| --- | --- |
| Provider ID | `blender` |
| Network endpoint | `POST http://<host>:8008/mcp/` (Streamable HTTP, stateless; trailing slash — bare `/mcp` 307-redirects) |
| Health | `GET http://<host>:8008/healthz` (unauthenticated liveness) |
| Primary credential | `Authorization: Bearer <token>` |
| Compatibility credential | `X-API-Key: <token>` (same single auth layer) |
| Token source | `BLENDER_MCP_TOKEN` env / secret manager, never Git |
| Failure codes | `401` missing/invalid identity · `403` denied |

## Gateway catalog

Bare provider tools canonicalize to `blender.<tool>` (idempotent when already
canonical). Minimum wiring:

```text
blender.help
blender.system_status
blender.system_capabilities
blender.get_scene_info
blender.get_object_info
blender.undo / blender.redo
blender.export_fbx / blender.export_gltf
```

## Contract drift detection

After `help`, pin `contract_hash` (SHA-256 over `docs/TOOL_GUIDE.md`).
Re-fetch `help` when the hash changes; treat a changed hash as a new
contract version (`cdt-blender-contract-v8` at this revision).

## Refusals the gateway must expect

- `unsupported_capability` (`retryable: false`): transactions, UV unwrap,
  brush strokes, masks, face sets, multiresolution, quarantined discipline
  builders.
- `validation_error`: file arguments outside `BLENDER_ALLOW_ROOTS`.
- `timeout`: bounded render/export budgets; a timeout is NOT proof of
  cancellation — re-query state before retrying.
- `provider_unavailable`: Blender addon offline (`system_status.addon.connected`
  is the preflight signal; `help` and design-rule tools still answer).

## Verified runtime baseline

Native provider acceptance is verified against exactly **Blender 4.5.3 LTS on Windows 11**. Legacy addon metadata uses 4.5.3 as its minimum version, while `system_capabilities.runtime_support` marks every other version/platform `unverified`. The accepted live matrix covers no active object, OBJECT, EDIT_MESH and SCULPT; authenticated provider-local MCP acceptance covers health, `help`, status/capabilities, auth rejection, and cube create → common `object_get` read-back. This still must not be used to claim unfinished modeling/sculpt capabilities ready.

## Windows-native deployment (no Docker)

Blender (UI context, sculpt, render) is Windows-bound, so this provider
deploys as a native process pair — no container image is shipped:

```powershell
pip install -e .                    # or pip install cdt-blender
$env:BLENDER_MCP_TOKEN = (Get-Secret blender_mcp_token)
cdt-blender serve --host 127.0.0.1 --port 8008
```

1. Start Blender, enable the `blender_mcp_addon`, press **Start MCP Server**.
2. Serve the bridge (fail-closed without the token).
3. Persist via Task Scheduler / NSSM; probe `GET /healthz` for liveness.
4. Keep the bridge bound to loopback; terminate TLS/exposure at the edge
   (reverse proxy / Cloudflare Tunnel).

## Unreal Engine 5 lane (future)

Blender-side interchange is ready: `export_fbx` (Blender-native axes,
convert on UE5 import) and `export_gltf`. The UE5 provider itself is a
separate future lane (Windows, Unreal Python/Remote Control) and needs no
Blender-side changes beyond these two tools.

## Standard §16 checklist status

- [x] Streamable HTTP `/mcp` · [x] Bearer fail-closed ·
  [x] credentials externalized · [x] explicit tool schemas · [x] read-only
  `help` versioned/fingerprinted · [x] stable IDs · [x] documented errors ·
  [x] health defined · [x] bounded total bridge→addon deadlines (120 s default; 2 s runtime-context discovery) ·
  [x] no credential logging · [x] `<provider>.<tool>` namespace ·
  [x] business logic stays in provider ·
  [x] provider-local authenticated MCP discovery + safe native create/read-back ·
  [ ] gateway-side catalog/policy discovery + safe-call test (SlncTrZ-MCP lane; external to this repo)
