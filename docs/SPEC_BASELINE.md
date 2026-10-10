# Spec Baseline — CDT-Blender

> Pinned: 2026-09-09
> Architecture source: `SlncTrZ/CDT_Engineer@643019c`

## Pinned inputs

| Local snapshot | Source at `643019c` |
| --- | --- |
| `specs/MCP_PROVIDER_STANDARD.md` | `MCP_PROVIDER_STANDARD.md` |
| `specs/ARCHITECTURE.md` | `docs/ARCHITECTURE.md` |
| `specs/CONTRACTS.md` | `docs/CONTRACTS.md` |

## Rules

- `specs/**` is read-only provider input.
- `CDT_Engineer` owns architecture/common-contract changes.
- This repo owns Blender extension semantics and runtime implementation.
- Never silently track hub `main`; spec updates require an explicit pin update and conformance review.
- No runtime import from another CDT provider repository.
- Modeling and Sculpting remain first-class native lanes; do not reduce Blender to generic render/object control.

## L2 Blender motion-graphics extension (separate pin)

- Provider-specific L2 normative contract: `CDT_Engineer@ce66840`,
  `docs/BLENDER_MOTION_GRAPHICS_EXTENSION_CONTRACT.md` (version `0.1.0`).
- CDT-Blender MCP contract `cdt-blender-contract-v10`; 7 new bounded L2
  tools, 121 MCP tools total. This does **not** alter the pinned common CAD
  `643019c` inputs or silently synchronize `specs/**`.
- The Engineer source commit has been validated locally but **not pushed**;
  remote publication and matching installed addon deployment are separate
  release gates. Source native/dispatch proof is Blender 4.5.3 headless on
  Windows, not a claim for the current UI session or Blender 5.x.

## Scope

This pin identifies shared inputs. Current capabilities and acceptance limits belong to the [runtime guide](TOOL_GUIDE.md).
