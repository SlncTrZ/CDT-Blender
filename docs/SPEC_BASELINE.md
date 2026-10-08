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

## Scope

This pin identifies shared inputs. Current capabilities and acceptance limits belong to the [runtime guide](TOOL_GUIDE.md).
