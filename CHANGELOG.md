# Changelog — CDT-Blender

Upstream history lives in the upstream repository (seehiong/blender-mcp-bridge).
CDT fork entries are marked `[CDT]`. See `ATTRIBUTION.md` (upstream pin
`b8113ae`, v0.1.3).

## [0.2.0] — Stable CDT-Blender motion graphics L2 — 2026-10-10

- Stable package version `0.2.0` with unchanged `cdt-blender-contract-v10` and 121 tools.
- Git release format `v.0.2.0`; no prerelease suffixes. Published RC retained as history.
- Production Gateway installation remains a separate promotion and auth gate.

## [0.2.0rc1] — Historical release candidate — 2026-10-10

- Source-verified 121-tool bridge, including seven bounded L2 SVG, GPv3,
  Geometry Nodes and Unicode/externally-shaped raster typography tools.
- Live remote authenticated Gateway→Windows agent→addon tests passed all
  seven L2 commands headless plus three commands in real Blender UI.
- Local Windows Blender 4.5.3 LTS .blend reopen, packed Arabic image,
  animation frame readback and op_id/allow-root refusal tested.
- Isolated cross-platform offline suite 2634 PASS on Windows and Linux.
- L2 invalid-argument errors return typed nonretryable validation_error.
- Release channel: **RC/canary**; production deployment requires a separately
  pinned source wheel, addon/runtime version match, credential-preserving
  migration and post-install authentication readback. Does not imply
  Blender 5.x verification or finished marketing footage.

## [0.1.3+cdt.1 — historical unreleased fork]

### [CDT] SlncTrZ provider-shell fork

- Stable provider ID `blender`; package `cdt-blender` (`blender-mcp-bridge`
  console alias retained).
- New read-only tools `help`, `system_status`, `system_capabilities`
  (answered locally from runtime `docs/TOOL_GUIDE.md`, SHA-256
  `contract_hash`; work while Blender is offline).
- Fail-closed Bearer auth on `/mcp` (`BLENDER_MCP_TOKEN`, `X-API-Key`
  compatibility through one layer); unauthenticated `GET /healthz`;
  loopback-first bind default.
- Path allow-roots (`BLENDER_ALLOW_ROOTS`, fail-closed `validation_error`).
- Removed in-provider LLM assistant (`assistant.py`, `/assistant/*`, model
  keys and the `anthropic` dependency).
- Removed Studio/views/models static mounts from the provider surface.
- Quarantined discipline builders (`architectural`, `systems`) from the
   contract: 98 → 90 upstream tools advertised at fork time (8 held out;
   current surface at `f60cf30`, verified 2026-10-06: 110 advertised MCP
   tools — 108 in `docs/tools.md` categories + lifecycle
   `reconcile_operation` / `operation_status`; quarantine list lives in
   `scripts/gen_tools_doc.py`).
- Added `export_fbx` / `export_gltf` interchange tools (Unreal Engine 5 lane).
- Sculpting honesty: deterministic assists only; strokes/masks/face-sets/
  multires declared unsupported in the capability map.

### [CDT] H14 — modeling UV + sculpt mask baseline

- Modeling UV unwrap/projection: `unwrap_mesh` (ANGLE_BASED/CONFORMAL) and
  `smart_project` with measurable UV read-back (layers, loops, non-zero
  coordinates); `blender.modeling.uv` capability now supported.
- Sculpt mask clearing/inversion: `clear_sculpt_mask` / `invert_sculpt_mask`
  as deterministic whole-mask attribute writes (background-safe, no viewport);
  `blender.sculpt.masks` capability now supported for clear/invert only.
- Contract bump `cdt-blender-contract-v8` → `v9`; `docs/tools.md` regenerated
  (112 categories). Brush strokes, mask painting, face sets and
  multiresolution remain unsupported.
