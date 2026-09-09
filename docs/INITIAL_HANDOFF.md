# Initial Handoff — Agent B / Blender

## Repository

- Path: `/mnt/pc-dev/CDT-Blender`
- GitHub: `SlncTrZ/CDT-Blender`
- Branch: `main`
- Governing hub pin: `CDT_Engineer@643019c`

## Read first

1. `AGENTS.md`
2. `docs/SPEC_BASELINE.md`
3. `docs/ROADMAP.md`
4. `specs/MCP_PROVIDER_STANDARD.md`
5. `specs/ARCHITECTURE.md`
6. `specs/CONTRACTS.md`
7. `README.md`

## Starting state

Clean provider-native skeleton. No AutoCAD/SketchUp/SolidWorks runtime code is present. Blender reference projects listed in the roadmap are MIT research inputs only.

## First task

Research the supported Blender-version/Python/context matrix and choose the addon/bridge boundary. Implement B0 identity/status/capability context and a real Blender smoke test before expanding B1 modeling.

## Restrictions

Do not modify another provider repo. Treat `CDT_Engineer` as read-only. Do not claim UI/sculpt operations from background contexts that cannot execute them reliably.
