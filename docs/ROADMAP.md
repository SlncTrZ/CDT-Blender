# PLAN — Blender Provider

> Lane: B · Target repo: `CDT-Blender` · Updated: 2026-09-14
> Governing docs: `MCP_PROVIDER_STANDARD.md`, `docs/ARCHITECTURE.md`, `docs/CONTRACTS.md`

## 1. Objective

Build a Blender MCP provider in an independent parallel delivery lane whose completion criteria explicitly require both:

1. **Modeling**
2. **Sculpting**

Scene setup/rendering is important but is not sufficient to call the Blender provider complete.

### Current verified checkpoint — 2026-09-14

B0 remains **IN PROGRESS**. Native Blender 4.5.3 LTS acceptance on Windows 11 currently covers:

- bounded runtime-context discovery with offline fail-closed behavior;
- `.blend` document new/open/info/save/save-as/close semantics with contained paths;
- deterministic active-scene object list/get/count;
- collection-backed `organization_list` with hierarchy/visibility metadata;
- explicit common `object_move`, `object_rotate` and `object_scale` semantics with parented-object read-after-write verification.

Live UI/addon lifecycle acceptance now passes on Blender 4.5.3 LTS / Windows 11: isolated-profile enable, start/stop/restart, bridge-to-addon runtime queries, and queue-timer survival across `document_new` are verified. Still required before B0 can close: final supported-version/context-matrix closure and the remaining B0 integration gates. This checkpoint does **not** relax the completion invariant: Modeling and Sculpting remain mandatory end-to-end lanes.

## 2. Runtime Architecture

Preferred direction:

```text
MCP provider
   ↓
Blender extension contract
   ↓
context-aware bpy bridge/addon
   ↓
Blender process
```

A background/headless engine may coexist for deterministic file/scene/render operations, but it must not claim interactive modeling/sculpt capabilities that need a valid Blender UI/context.

External research provenance and upstream pins are recorded in `ATTRIBUTION.md`. Local reference checkouts are non-contract development inputs and are intentionally excluded from the repository.

Reuse behavior/tests/bridge patterns selectively; normalize public contract to CDT/SlncTrZ.

## 3. Common Contract Mapping

| Common semantic | Blender mapping |
| --- | --- |
| document lifecycle | `.blend` file / scene state |
| object query | Blender objects/data blocks |
| organization | collections |
| transforms | object/edit transforms |
| units/coordinates | scene units + world/local/object space |
| selection | object/edit/sculpt selection/context |
| import/export | supported mesh/scene formats |
| validation | mesh/topology/object inspection |

## 4. Blender Extension Contract

### 4.1 Modeling — mandatory

Required families:

- object lifecycle;
- mode switching with explicit context checks;
- mesh creation;
- vertices/edges/faces query;
- topology selection;
- extrude;
- inset;
- bevel;
- loop/ring operations where deterministic;
- merge/split;
- normals;
- modifiers;
- transform/apply transforms;
- collections;
- UV operations;
- materials;
- topology/manifold inspection.

### 4.2 Sculpting — mandatory

Required families:

- enter/exit sculpt mode;
- brush discovery/selection;
- brush settings;
- deterministic stroke execution where Blender API/context permits;
- masks;
- face sets;
- symmetry;
- voxel remesh;
- dynamic topology (dyntopo);
- multiresolution workflow;
- mesh density/topology inspection before and after sculpt operations.

Sculpt tool behavior must specify coordinate/frame semantics for strokes and whether an active area/region/context is required.

### 4.3 Scene / Material / Render

- cameras;
- lights;
- scene/world settings;
- materials/textures;
- render engine/settings;
- render image;
- export assets.

### 4.4 Future extension

Animation, rigging, geometry nodes and simulation are future extension families. They are not prerequisites for the initial Blender provider unless roadmap changes explicitly.

## 5. Capability Context

Blender is highly context-sensitive. `system_capabilities` should distinguish at least:

```text
backend/process available
UI context available
active object available
active mode
mesh editable
sculpt context available
render engine available
```

A capability may be supported by the provider but temporarily unavailable because runtime context is missing. Error semantics should distinguish:

- unsupported capability;
- invalid context/state;
- validation error;
- provider unavailable.

## 6. Implementation Phases

Lane B is independent: it may start from the approved CDT contracts immediately and must not import runtime code from AutoCAD, SketchUp or SolidWorks. Shared implementation is considered only after equivalent behavior is proven across providers.

### B0 — Bridge + Identity

- SlncTrZ compliance;
- reliable connection to Blender;
- `help`, status, capability map;
- file/scene info;
- object list/get;
- basic primitives/transforms;
- integration tests.

### B1 — Modeling Baseline

- mesh edit mode;
- vertices/edges/faces;
- topology edits;
- extrude/inset/bevel;
- modifiers;
- collections;
- materials;
- UV baseline;
- correctness fixtures.

### B2 — Sculpting Baseline

- sculpt context validation;
- brush control;
- strokes;
- mask/face sets;
- symmetry;
- voxel remesh;
- dyntopo;
- multires;
- topology health/correctness tests.

### B3 — Scene/Render Hardening

- cameras/lights;
- render;
- export;
- timeout handling for long renders;
- artifact/result metadata.

### B4 — Scalability

Only after measurements:

- tool profiles/discovery if needed;
- batch operations;
- large scene latency optimizations;
- context cache only if invalidation is provably correct.

## 7. Safety / Correctness

- No arbitrary Python execution tool by default.
- Context transitions must be explicit and validated.
- Destructive mesh operations must be clearly named/documented.
- Long operations such as remesh/render need bounded timeout semantics.
- Report topology changes honestly; do not pretend a sculpt stroke is deterministic if API/context prevents reproducibility.
- Save/export paths must stay inside configured roots.

## 8. Completion Gate

Blender baseline is complete only when:

- Modeling lane passes end-to-end;
- Sculpting lane passes end-to-end;
- scene/render baseline works;
- capability/context reporting matches runtime;
- SlncTrZ integration checklist passes;
- tests cover topology-impacting sculpt/model operations.

A provider that only creates primitives and renders scenes is **not complete**.
