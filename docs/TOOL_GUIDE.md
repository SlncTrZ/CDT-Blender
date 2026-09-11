# CDT-Blender Tool Guide (runtime contract source)

> This file is the runtime-readable operating guide for the CDT-Blender provider.
> The `help` tool serves this exact file content (plus version/fingerprint fields)
> so clients always read the running contract, not a stale copy.
> Fork: CDT-Blender adapts upstream `seehiong/blender-mcp-bridge` (MIT) to the
> SlncTrZ MCP Provider Standard. See `ATTRIBUTION.md`.

## Provider identity

- Provider ID: `blender` (stable, lowercase ASCII).
- Gateway canonical tools: `blender.<tool>` (e.g. `blender.help`, `blender.create_primitive`).
- Bare tool names are advertised by this provider; SlncTrZ-MCP owns namespacing.

## Transport

- Network mode: Streamable HTTP `POST /mcp/` (stateless; MCP 2025-06-18; trailing slash — bare `/mcp` 307-redirects).
- Health (unauthenticated, side-effect free): `GET /healthz` returns
  `{ status, provider, provider_version, contract_version }`.
- Bridge defaults: `MCP_BRIDGE_HOST=127.0.0.1`, `MCP_BRIDGE_PORT=8008`.
- Execution path: MCP client → bridge (`blender_mcp_bridge`) → local TCP
  socket → in-Blender addon (`blender_mcp_addon`) → `bpy`. The addon socket
  defaults to `127.0.0.1:8888` (`BLENDER_ADDON_HOST`/`BLENDER_ADDON_PORT`).
- Start Blender first, enable the addon, press **Start MCP Server** in the
  sidebar; then `cdt-blender serve`. `system_status` reports addon
  reachability (socket probe, no side effects).

## Authentication

- Primary: `Authorization: Bearer <token>`.
- Compatibility: `X-API-Key: <token>` (same single authorization layer).
- Token source: `BLENDER_MCP_TOKEN` environment variable / secret manager.
  Never in URLs, tool args, logs, or Git-tracked config.
- Fail-closed: the server refuses to serve without a token unless
  `MCP_ALLOW_UNAUTHENTICATED=1` is set explicitly for local loopback testing.
- Failures: `401` missing/invalid identity, `403` valid identity but denied.

## Discovery tools (call by bare name)

- `help` — read-only operating contract (this guide + versions + fingerprint).
- `system_status` — liveness, versions, addon reachability. No side effects.
- `system_capabilities` — machine-readable capability map (see below).
- Design-rule advisory (`check_design`, `get_design_rules`,
  `list_design_topics`) answers from a local JSON file — milliseconds, no
  network, no Blender needed.

Every tool is callable by name. Do not invent tool names.

## Capability map (honest subset)

`system_capabilities` reports this shape; unsupported means a typed refusal,
never fake success:

- `common.document.{new,open,info,save,save_as,close}` — supported (`.blend`/scene).
- `common.object.{list,get,count}` — supported (objects/data blocks).
- `common.organization.list` — supported (collections).
- `common.transform.{move,rotate,scale}` — supported (object/edit transforms).
- `common.transaction.*` — UNSUPPORTED (`reason: no_atomic_transaction_use_undo_history`).
  Native `undo`/`redo` ARE supported; mutating addon commands push undo steps.
- `common.import_asset` / `common.export_asset` — supported (STL/3MF/OBJ +
  FBX/glTF interchange).
- `common.validate.*` / `common.inspect` / `common.measure` — supported
  (manifold checks, object info, distances).
- `blender.modeling.*` — supported (primitives, curves, modifiers, operators).
  UV unwrap: UNSUPPORTED (`no_uv_unwrap_tool_yet`).
- `blender.sculpt.assist` — supported deterministic assists (smooth, inflate,
  grab, symmetrize, dyntopo toggle). Brush strokes, masks, face sets and
  multiresolution: UNSUPPORTED until proven in a valid sculpt context.
- `blender.scene.render` — supported (bounded timeouts; a timeout is NOT
  proof of cancellation — re-query state before retrying).
- `blender.interchange.{fbx,gltf}` — supported. FBX exports Blender-native
  axes (`-Z` forward, `Y` up); convert on Unreal Engine 5 import.
- Discipline builders (architectural rooms/walls, MEP pipe/cable-tray
  systems) are NOT in this contract — quarantined to CDT_Engineer domains.

## Safety rules every client must respect

1. Validate inputs before side effects; unknown fields are rejected.
2. File arguments (`filepath`, `image_path`) must sit under
   `BLENDER_ALLOW_ROOTS` (defaults to the assets dir or cwd); violations
   fail with `validation_error` before Blender is contacted.
3. Writes are destructive by name (`delete_*`, `remove_*`, `apply_*` bake
   data); ordinary edits vs destructive ops are separated in descriptions.
4. Context matters: UI-context capabilities need a running Blender with the
   addon started. Headless/background use is limited to deterministic
   file/scene operations — never claim interactive results from it.
5. Engineering interpretation (standards compliance, Audit Reports) belongs
  to CDT_Engineer Production Domains — this provider reports 3D facts
  (geometry, topology, measurements) only.

## Error vocabulary

`authentication_error | authorization_error | validation_error | not_found |
conflict | rate_limited | timeout | provider_unavailable | internal_error |
unsupported_capability`. Errors never include credentials, tokens, or stack
traces. Each error states whether retry is reasonable.

## Versioning

- `provider_version` — this software build (semver + `-cdt.N` fork suffix).
- `contract_version` — this help/tool contract (`cdt-blender-contract-v1`).
- `common_contract_version` — applied CDT common semantics (`cdt-common-v1`).
- `protocol_version` — MCP protocol / SDK compatibility declaration.
- `contract_hash` — SHA-256 over this guide's canonical content; clients and
  the gateway use it to detect contract drift.
