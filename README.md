# CDT-Blender

Independent Blender MCP provider for the CDT engineering program (SlncTrZ provider: `blender`).

> **Fork.** CDT-Blender adapts upstream
> [seehiong/blender-mcp-bridge](https://github.com/seehiong/blender-mcp-bridge)
> (MIT, © 2026 seehiong — `LICENSE` preserved verbatim) to the SlncTrZ
> ecosystem. Upstream pin: `b8113ae` (v0.1.3). This fork: `0.1.3+cdt.1`.
> Full provenance in [`ATTRIBUTION.md`](ATTRIBUTION.md).
>
> **SlncTrZ compliance:** stable provider ID `blender`
> (`blender.<tool>` gateway namespace) · Streamable HTTP `POST /mcp` ·
> fail-closed Bearer auth · read-only `help` / `system_status` /
> `system_capabilities` from runtime [`docs/TOOL_GUIDE.md`](docs/TOOL_GUIDE.md)
> with SHA-256 `contract_hash` · unauthenticated `GET /healthz`.
> Call `help` first — it is the running contract.
>
> **Boundary (CDT_Engineer):** generic native 3D execution only. Discipline
> builders (architectural/MEP) are quarantined from the contract; standards
> interpretation and Audit Reports belong to CDT_Engineer Production Domains.
>
> Status: **B0 baseline IN PROGRESS** · Native acceptance verified on **Blender 4.5.3 LTS / Windows 11** for runtime context discovery, document lifecycle, object query, organization listing and common transforms · Spec pin: `CDT_Engineer@643019c`

## Repository role

This repo owns Blender-native runtime code, tests, bridge/addon behavior and provider documentation. Common architecture/contracts live in `SlncTrZ/CDT_Engineer`; pinned read-only snapshots are under `specs/`.

## Completion invariant

Blender baseline requires both **Modeling** and **Sculpting** end-to-end. Primitive creation or rendering alone is not sufficient.

## First objective

B0 proves the supported Blender-version/context matrix and bridge/addon lifecycle, then delivers:

- provider identity/help/status/capabilities;
- explicit UI/headless/context reporting;
- file/scene info;
- object list/get;
- primitives/transforms;
- real Blender integration tests.

Current verified checkpoint (2026-09-14): B0 runtime discovery, document lifecycle, common object query, collection-backed organization listing, explicit common transforms, and live UI/addon lifecycle have native acceptance on Blender 4.5.3 LTS. B0 is **not complete** until the supported-version/context matrix and remaining B0 integration gates are closed.

## Start here

1. Read `docs/SPEC_BASELINE.md` and `docs/ROADMAP.md`.
2. Read `specs/MCP_PROVIDER_STANDARD.md`, `specs/ARCHITECTURE.md` and `specs/CONTRACTS.md`.
3. Read `docs/TOOL_GUIDE.md` and `docs/SLNCTRZ_INTEGRATION.md`.
4. Research current `bpy` context behavior before changing the bridge boundary.

Agent-local working instructions are supplied by the execution environment and are intentionally not part of the public repository. External research provenance is recorded in `ATTRIBUTION.md`.
