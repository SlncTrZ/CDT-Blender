# Attribution & Fork Notice — CDT-Blender

## Upstream

CDT-Blender is a fork of **blender-mcp-bridge** by **seehiong**
(<https://github.com/seehiong/blender-mcp-bridge>), licensed under the
**MIT License** (see `LICENSE` — copyright `Copyright (c) 2026 seehiong`,
preserved verbatim as required).

Upstream pin: `b8113aea74aeb08b8b83ea08989ae53d729ed82b`
(2026-08-23, release `v0.1.3`) — structured HTTP MCP bridge (98 tools) +
in-Blender addon, TCP command dispatch, session record/playback, 3D-print
design-rule advisory. `blender-mcp` by ahujasid was evaluated and rejected
as a fork base: its capability surface is arbitrary `exec()` inside Blender,
which the CDT-Blender lane forbids; it remains a behavior reference only.

Copied: `blender_mcp_bridge/`, `blender_mcp_addon/`, `data/design-rules.json`,
`scripts/`, `tests/`, CI workflow, `LICENSE`.
Excluded: `studio/` (web UI), `community/` (example builds), `.claude/`,
container/registry publishing workflows.

## What the fork changes (and why)

CDT-Blender keeps upstream Blender execution mechanics and adapts the
**provider shell** to the SlncTrZ ecosystem:

- Stable provider ID `blender` (`blender.<tool>` gateway namespace).
- Read-only `help` / `system_status` / `system_capabilities` tools served
  from runtime `docs/TOOL_GUIDE.md` with SHA-256 `contract_hash`.
- Fail-closed Bearer auth (`BLENDER_MCP_TOKEN`), `X-API-Key` through one
  auth layer; `GET /healthz` stays unauthenticated liveness.
- Loopback-first defaults (`127.0.0.1`); path allow-roots enforced
  (`BLENDER_ALLOW_ROOTS`, fail-closed `validation_error`).
- Removed: in-provider LLM assistant endpoints (`assistant.py`,
  `/assistant/*` routes and keys) — providers own deterministic mechanics,
  never LLM judgment or third-party model credentials.
- Quarantined from the contract (code retained, not advertised): discipline
  builders (`architectural`, `systems` — rooms/walls/pipes/cable trays).
  Discipline objects belong to CDT_Engineer Production Domains.
- Added: `export_fbx` / `export_gltf` interchange tools (Unreal Engine 5 lane).
- Sculpting honesty: deterministic assists only (smooth/inflate/grab/
  symmetrize/dyntopo); brush strokes, masks, face sets and multiresolution
  are declared unsupported until proven in a valid sculpt context.

No upstream execution logic was removed besides the assistant surface;
no upstream license term was altered. New CDT files carry this fork header.

## License

- Upstream code: MIT (`LICENSE`, seehiong).
- CDT adaptation files: same MIT License, copyright
  `SlncTrZ / Truong Cong Dinh` for the adaptation layer only, upstream
  copyright preserved. Neither party's notice may be removed.
