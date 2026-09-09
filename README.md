# CDT-Blender

Independent Blender MCP provider for the CDT engineering program.

> Status: **B0 skeleton ready** · Runtime implementation not started · Spec pin: `CDT_Engineer@643019c`

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

## Start here

1. Read `AGENTS.md`.
2. Read `docs/INITIAL_HANDOFF.md` and `docs/ROADMAP.md`.
3. Read `docs/SPEC_BASELINE.md` plus `specs/**`.
4. Research current `bpy` context behavior before choosing the bridge boundary.

References listed in the roadmap are MIT-licensed research inputs; adapt behavior/tests selectively rather than inheriting their public contract.
