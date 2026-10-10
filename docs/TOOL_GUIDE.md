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

## Verified runtime baseline

- The single native acceptance baseline is **Blender 4.5.3 LTS on Windows 11**.
- Legacy addon metadata therefore declares Blender **4.5.3** as its minimum version. That field is only a minimum-version gate; it is not evidence that later Blender versions are supported.
- `system_capabilities.runtime_support.policy=verified_native_baseline_only`. Only Blender 4.5.3 on Windows classifies as `runtime_context.runtime_support_status=verified_native_baseline`; every other version/platform is reported as `unverified_runtime`, not silently supported or rejected.
- Native context evidence covers background discovery plus live UI with no active object, OBJECT, EDIT_MESH and SCULPT. `mesh_editable=true` is verified only for the EDIT_MESH row; `sculpt_context_available=true` is verified only for the SCULPT row with an active mesh and VIEW_3D window context.
- Background-mode fixtures cover deterministic document/object/organization/transform operations. Live UI/addon lifecycle is verified using an isolated profile: enable, start/stop/restart/disable, bridge-to-addon queries, and queue-timer survival across `document_new`.
- These B0 context facts are preflight data, not a blanket claim that every later modeling/sculpt operation is complete; tool-specific requirements and unsupported capability declarations still apply.

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
- Timeouts are layered and bounded: addon command wait `60s`
  (`COMMAND_WAIT_TIMEOUT_SECONDS`) < bridge transport default `120s`
  (`BLENDER_TRANSPORT_TIMEOUT_SECONDS`) so the addon's typed timeout reaches
  the caller instead of being masked as a transport timeout; discovery probe
  `2s`; request receive `5s`. A timeout is NOT proof of cancellation —
  re-query state before retrying a mutation.

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
- `system_capabilities` — machine-readable implemented capability map, the evidence-backed `runtime_support` matrix, plus a bounded live `runtime_context` snapshot from the Blender addon when available.
- Design-rule advisory (`check_design`, `get_design_rules`,
  `list_design_topics`) answers from a local JSON file — milliseconds, no
  network, no Blender needed.

Every tool is callable by name. Do not invent tool names.

## Capability map (honest subset)

`system_capabilities` reports static implementation support plus `runtime_support` and `runtime_context` facts for the current Blender process. Unsupported means a typed refusal, never fake success. Version/platform evidence is separate from feature support: an otherwise callable runtime outside the verified 4.5.3/Windows baseline is marked `unverified_runtime`. When the addon is offline or its context query cannot complete within the bounded discovery deadline, `runtime_context.context_available=false` with a stable reason:

- `common.document.{new,open,info,save,save_as,close}` — supported by public `document_*` tools. Open/save paths are restricted to configured allow-roots; `document_close` preserves the Blender process/addon by resetting to an empty unsaved file instead of quitting Blender. In background mode Blender 4.5 does not provide a reliable clean/dirty signal, so destructive replace/open/close requires explicit `discard_unsaved=true`.
- `common.object.{list,get,count}` — supported by public `object_*` tools scoped to the active scene. Lists are deterministic and bounded. Blender `session_uid` is exposed only as a non-persistent process-scoped native handle; object names remain the current lookup key.
- `common.organization.list` — supported by public `organization_list`, mapping only collections reachable from the active scene. Results are deterministic and bounded; hierarchy, direct object counts and Blender visibility state are reported without treating orphan data-blocks as active-scene organizations.
- `common.transform.{move,rotate,scale}` — supported by public `object_move/object_rotate/object_scale`. Move is a relative WORLD-space XYZ delta; rotate is a WORLD-space Euler XYZ delta in degrees about the object origin and fails closed on sheared world matrices; scale multiplies LOCAL-axis object scale channels. The legacy `transform_object` remains a Blender extension for absolute/channel-oriented edits.
- `common.transaction.*` — UNSUPPORTED (`reason: no_atomic_transaction_use_undo_history`).
  Native `undo`/`redo` ARE supported; mutating addon commands push undo steps.
- `common.import_asset` / `common.export_asset` — supported (STL/3MF/OBJ +
  FBX/glTF interchange).
- `common.validate.*` / `common.inspect` / `common.measure` — supported
  (manifold checks, object info, distances).
- `blender.modeling.*` — supported (primitives, curves, modifiers, operators,
  UV unwrap/projection via `unwrap_mesh` and `smart_project`).
- `blender.sculpt.assist` — supported deterministic assists (smooth, inflate,
  grab, symmetrize, dyntopo toggle). Mask clear/invert are supported as
  deterministic whole-mask attribute writes; brush strokes, mask painting,
  face sets and multiresolution: UNSUPPORTED until proven in a valid sculpt
  context.
- `blender.scene.render` — supported (bounded timeouts; a timeout is NOT
  proof of cancellation — re-query state before retrying).
- `blender.interchange.{fbx,gltf}` — supported. FBX exports Blender-native
  axes (`-Z` forward, `Y` up); convert on Unreal Engine 5 import.
- Discipline builders (architectural rooms/walls, MEP pipe/cable-tray
  systems) are NOT in this contract — quarantined to CDT_Engineer domains.

## Safety rules every client must respect

1. Validate inputs before side effects; unknown fields are rejected.
2. File arguments (`filepath`, `image_path`) and render/output paths
   (`output_path`, `output_dir`, export/import destinations, including
   absolute and Blender-relative `//` paths) must sit under
   `BLENDER_ALLOW_ROOTS` (defaults to the assets dir or cwd); violations
   fail with `validation_error` before/without touching Blender state.
   Symlink/junction escapes are resolved before the check.
3. Writes are destructive by name (`delete_*`, `remove_*`, `apply_*` bake
   data); ordinary edits vs destructive ops are separated in descriptions.
4. Context matters: UI-context capabilities need a running Blender with the
   addon started. Background use is limited to the deterministic operations
   actually proven by native fixtures; never infer VIEW_3D/edit/sculpt readiness
   from background success. Preflight `runtime_context` before context-sensitive work.
5. Engineering interpretation (standards compliance, Audit Reports) belongs
  to CDT_Engineer Production Domains — this provider reports 3D facts
  (geometry, topology, measurements) only.

## Error vocabulary

`authentication_error | authorization_error | validation_error | not_found |
conflict | rate_limited | timeout | provider_unavailable | internal_error |
unsupported_capability`. Errors never include credentials, tokens, or stack
traces. Each error states whether retry is reasonable.

## Blender L2 motion-graphics extension (contract v10)

Seven additive public tools are available in builds that include the matching
bridge **and** in-Blender addon. Do not infer availability from source history;
preflight `system_status`, attached addon generation/runtime context, and
`system_capabilities` before mutation. No upgrade is claimed for the user's
already-running addon.

| Tool | Native scope / required verification |
| --- | --- |
| `import_svg_curves` | offline basic SVG with bounded whitelisted inline presentation styles; contains file within workstation allow-roots; CURVE object count/name/scale readback |
| `create_grease_strokes` | Grease Pencil v3 bounded strokes and held-frame reveal; object type, drawing frames and points |
| `create_filled_grease_tween` | same-topology, closed GPv3 polygon fill and LINEAR/SMOOTHSTEP point interpolation across held frames |
| `create_particle_preset` | curated LINE/RING Geometry Nodes; bounded instances and rotation keyframes |
| `create_animated_particle_grid` | curated rows/columns wave grid (≤512 instances) with keyed 4D Noise displacement |
| `create_unicode_text` | native NFC Vietnamese/Latin multiline text with optional allow-root local font; refuses Arabic/Indic/RTL shaping |
| `create_shaped_text_plane` | load bounded RGBA PNG shaped previously by RAQM/HarfBuzz/FriBidi, import as transparent textured plane and pack image into .blend; glyphs **not editable text/vector** |

Complex Arabic/Hindi shaping uses a **separate offline raster preprocessor**
`scripts/infographic_shape_text_asset.py` on a host with Pillow RAQM and
explicit locally supplied font files. It does not transmit or redistribute
font binaries; a missing shaping engine, font or allowed output root is a
typed blocker. The tool `create_shaped_text_plane` imports only a produced
PNG and does **not** execute arbitrary Python or invoke HarfBuzz inside Blender.

All seven tools use the normal mutation `op_id` lifecycle and native readback
policy. File-oriented operations receive workstation `_allow_roots` internally
from the bridge, never from user input. These are provider-specific **L2**
capabilities, not common CAD primitives. Older 114-tool clients remain
compatible; when an old addon is attached, L2 calls can fail as unsupported and
must not be retried blindly.

### Native qualification scope

Factory-startup Blender 4.5.3 Windows headless tests cover all seven addon
dispatch handlers, plus 3-frame SVG style/GP fill tween/GN wave/RAQM visual
qualification. Those tests do **not** prove Blender 5.x compatibility, live UI
motion editing, final production video quality or network gateway deployment.
For broader workflow claims, run isolated add-on lifecycle + real gateway E2E
with a matching package before enabling a release.

## Versioning

- `provider_version` — this software build (semver + `-cdt.N` fork suffix).
- `contract_version` — this help/tool contract (`cdt-blender-contract-v10`).
- `common_contract_version` — applied CDT common semantics (`cdt-common-v1`).
- `protocol_version` — MCP protocol / SDK compatibility declaration.
- `contract_hash` — SHA-256 over this guide's canonical content; clients and
  the gateway use it to detect contract drift.
