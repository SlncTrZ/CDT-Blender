# PLAN — Blender Provider

> Lane: B · Target repo: `CDT-Blender` · Updated: 2026-10-06
> Governing docs: `MCP_PROVIDER_STANDARD.md`, `docs/ARCHITECTURE.md`, `docs/CONTRACTS.md`

## 1. Objective

Build a Blender MCP provider in an independent parallel delivery lane whose completion criteria explicitly require both:

1. **Modeling**
2. **Sculpting**

Scene setup/rendering is important but is not sufficient to call the Blender provider complete.

### Current verified checkpoint — 2026-10-06

B0 baseline/context, B1 reliability, B2 modeling, B3 sculpting, and certification are **PASS** on the verified native baseline **Blender 4.5.3 LTS / Windows 11**. Acceptance covers:

- bounded runtime-context discovery with offline fail-closed behavior;
- `.blend` document new/open/info/save/save-as/close semantics with contained paths;
- deterministic active-scene object list/get/count;
- collection-backed `organization_list` with hierarchy/visibility metadata;
- explicit common `object_move`, `object_rotate` and `object_scale` semantics with parented-object read-after-write verification;
- isolated-profile addon enable/start/stop/restart/disable and queue-timer survival across `document_new`;
- live UI context rows for no active object, OBJECT, EDIT_MESH and SCULPT, with truthful `mesh_editable` / `sculpt_context_available` state;
- authenticated Streamable HTTP MCP health/discovery/status/capabilities;
- **Mutation lifecycle (R1 / BL-01, BL-02):** Stable `op_id`, cached receipts preventing duplicate side-effects, `expired_pending` non-dispatch, `timeout_uncertain` marking with dependent write lock, and `reconcile_operation` datablock verification;
- **Bounded execution & containment (R2 / BL-03, BL-04):** Bounded admission queue (16 items max), UI timer dispatch fairness (4 items/tick), central fail-closed path containment resolving `realpath` (blocking Windows symlinks/junctions);
- **Modeling & Sculpting (BL-05, BL-06):** Mesh primitives, bmesh extrude/edit, Sculpt mode lifecycle, and Blender 4.5.3 LTS dynamic topology (`use_dynamic_topology_sculpting`);
- **Full test suite:** 1616 tests passing, native execution manifest recorded at `_private/evidence/release_certification_4.5.3/manifest.json`.

The addon metadata minimum is 4.5.3 because Blender's legacy `bl_info.blender` field is a minimum-version declaration. `system_capabilities.runtime_support` treats only 4.5.3/Windows as the verified native baseline; other versions/platforms remain `unverified`.

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

A background/headless engine coexists for deterministic file/scene/render/mesh operations, but interactive modeling/sculpt capabilities that require an active OpenGL UI context must reflect truthful context availability.

External research provenance and upstream pins are recorded in `ATTRIBUTION.md`. Local reference checkouts are non-contract development inputs and are intentionally excluded from the repository.

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
| lifecycle / reconcile | `MutationLifecycleManager` / `reconcile_operation` |

## 4. Blender Extension Contract

### 4.1 Modeling — mandatory (COMPLETED)

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

### 4.2 Sculpting — mandatory (COMPLETED)

Required families:

- enter/exit sculpt mode;
- brush discovery/selection;
- brush settings;
- deterministic stroke execution where Blender API/context permits;
- masks;
- face sets;
- symmetry;
- voxel remesh;
- dynamic topology (dyntopo) compatible with Blender 4.5.3;
- multiresolution workflow;
- mesh density/topology inspection before and after sculpt operations.

Sculpt tool behavior specifies coordinate/frame semantics for strokes and whether an active area/region/context is required.

### 4.3 Scene / Material / Render (COMPLETED)

- cameras;
- lights;
- scene/world settings;
- materials/textures;
- render engine/settings;
- render image;
- export assets (STL, FBX, glTF).

### 4.4 Future extension

Animation, rigging, geometry nodes and simulation are future extension families. They are not prerequisites for the core Blender provider.

## 5. Capability Context

Blender is highly context-sensitive. `system_capabilities` distinguishes:

```text
backend/process available
UI context available
active object available
active mode
mesh editable
sculpt context available
render engine available
```

Error semantics distinguish:

- unsupported capability;
- invalid context/state;
- validation error;
- provider unavailable;
- timeout uncertain;
- uncertain predecessor blocked;
- rate limited (admission queue full).

## 6. Implementation Phases

### B0 — Bridge + Identity (PASS)
- SlncTrZ compliance; reliable connection to Blender; `help`, status, capability map; file/scene info; object list/get; basic primitives/transforms; integration tests.

### B1 — Reliability & Lifecycle (PASS)
- Stable `op_id`, mutation lifecycle, timeout uncertainty, reconcile operation, bounded admission queue, timer budget, path containment.

### B2 — Modeling Baseline (PASS)
- Mesh edit mode, vertices/edges/faces, topology edits, extrude/inset/bevel, modifiers, collections, materials.

### B3 — Sculpting Baseline (PASS)
- Sculpt context validation, mode switching, dynamic topology for Blender 4.5.3, smooth, inflate, grab falloff, symmetry.

### B4 — Operations & Certification (PASS)
- Render/export verification, native Blender 4.5.3 LTS release matrix, evidence manifest.

## 7. Safety / Correctness

- No arbitrary Python execution tool by default.
- Context transitions are explicit and validated.
- Destructive mesh operations are clearly named/documented.
- Long operations have bounded timeout semantics with uncertain receipt generation.
- Topology changes are reported honestly.
- Save/export paths stay inside configured roots (`require_allowed` with `realpath`).

## 8. Completion Gate

- Modeling lane passes end-to-end (PASS);
- Sculpting lane passes end-to-end (PASS);
- scene/render baseline works (PASS);
- capability/context reporting matches runtime (PASS);
- SlncTrZ integration checklist passes (PASS);
- tests cover topology-impacting sculpt/model operations (1616/1616 tests PASS).
