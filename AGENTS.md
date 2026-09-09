# AGENTS.md — CDT-Blender

## Role

Lane B owns the Blender MCP provider runtime only. `CDT_Engineer` is the architecture/spec/control source and is read-only to this lane.

## Governing spec baseline

- Source: `SlncTrZ/CDT_Engineer@643019c`
- Read first: `docs/SPEC_BASELINE.md`, `specs/MCP_PROVIDER_STANDARD.md`, `specs/ARCHITECTURE.md`, `specs/CONTRACTS.md`, `docs/ROADMAP.md`.
- `specs/**` is a pinned read-only snapshot; contract changes belong in `CDT_Engineer`.

## Ownership boundary

Allowed: `CDT-Blender/**` only.

Forbidden unless explicitly assigned:

- AutoCAD/SketchUp/SolidWorks runtime repositories;
- provider business logic in `CDT_Engineer`;
- importing runtime code from another provider;
- creating `CDT-Provider-Kit` before Rule-of-Two evidence;
- arbitrary Python execution tools;
- claiming interactive modeling/sculpt capability from a background context that cannot provide it.

## First objective — B0/B1

1. Prove the supported Blender-version/context matrix and bridge/addon lifecycle.
2. Implement provider identity/help/status/capabilities.
3. Distinguish UI context, headless/background context, active object and active mode.
4. Add file/scene info, object list/get, primitives and transforms.
5. Build the modeling baseline before expanding scene/render features.
6. Blender completion later requires both Modeling and Sculpting end-to-end; render-only is not sufficient.

## Required workflow

1. Follow the global SlncTrZ Agent Harness from `context.bootstrap`.
2. Research `bpy` context semantics before implementation; prefer deterministic data API calls where possible.
3. TDD and capability/context honesty tests are mandatory.
4. Mode/context transitions must be explicit and validated before side effects.
5. Long operations such as remesh/render require bounded timeout/result semantics.
6. Run focused + full tests and hygiene before commit.
7. Log every code/deploy change with CyberBrain `kb.knowledge_store`.
8. End each session with episodic save then `dream_enqueue`.
9. Commit/push only this repo; default branch `main` unless a task defines otherwise.

## Completion invariant

A Blender provider that only creates primitives or renders scenes is not baseline-complete. Modeling and Sculpting are mandatory capability lanes and must be verified in the correct Blender runtime/context.
