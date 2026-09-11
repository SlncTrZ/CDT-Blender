# Changelog — CDT-Blender

Upstream history lives in the upstream repository (seehiong/blender-mcp-bridge).
CDT fork entries are marked `[CDT]`. See `ATTRIBUTION.md` (upstream pin
`b8113ae`, v0.1.3).

## [Unreleased — CDT-Blender 0.1.3+cdt.1]

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
  contract: 98 → 90 upstream tools advertised.
- Added `export_fbx` / `export_gltf` interchange tools (Unreal Engine 5 lane).
- Sculpting honesty: deterministic assists only; strokes/masks/face-sets/
  multires declared unsupported in the capability map.
