# PLAN — Blender Provider

> Lane: B · Target repo: `CDT-Blender` · Updated: 2026-10-06
> Governing docs: `MCP_PROVIDER_STANDARD.md`, `docs/ARCHITECTURE.md`, `docs/CONTRACTS.md`

## 1. Objective

Build a Blender MCP provider in an independent parallel delivery lane whose completion criteria explicitly require both:

1. **Modeling**
2. **Sculpting**

Scene setup/rendering is important but is not sufficient to call the Blender provider complete.

### Current verified checkpoint — B0 PASS (certified-at: 2026-09-14 evidence, Blender 4.5.3 LTS / Windows 11)

B0 baseline/context is **PASS** on the verified native baseline **Blender 4.5.3 LTS / Windows 11**. B1 reliability is **PARTIAL** (bounded admission queue 16 / tick budget 4, pending expiry, uncertain-receipt and reconcile controls exist; client/heavy-op budgets and async hardening remain open). B2 modeling and B3 sculpting are **OPEN** mandatory gates: mesh primitives, bmesh edits, Sculpt mode lifecycle and dyntopo assists exist, but UV unwrap, brush strokes, masks, face sets and multiresolution are declared unsupported in `blender_mcp_bridge/provider_contract.py` and native acceptance is pending. B4 operations/certification is **PENDING**: the only native execution manifest (`_private/evidence/release_certification_4.5.3/manifest.json`) is historical source `39e2810` (2 rows), not a certification of the current HEAD. Acceptance covers:

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
- **Modeling & Sculpting (BL-05, BL-06 — OPEN):** Mesh primitives, bmesh extrude/edit, Sculpt mode lifecycle, and Blender 4.5.3 LTS dynamic topology (`use_dynamic_topology_sculpting`) assists exist; UV unwrap, brush strokes, masks, face sets and multiresolution remain declared unsupported pending native acceptance;
- **Offline test suite (pending native certification):** 1630 tests passing offline at `f60cf30` (verified 2026-10-06, no Blender); the native execution manifest at `_private/evidence/release_certification_4.5.3/manifest.json` is historical source `39e2810` (2 rows) and does not certify the current HEAD.

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

### 4.1 Modeling — mandatory (OPEN)

Required families (UV unwrap currently declared unsupported: `no_uv_unwrap_tool_yet`):

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

### 4.2 Sculpting — mandatory (OPEN)

Required families (brush strokes, masks, face sets and multiresolution currently declared unsupported pending valid sculpt-context proof):

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

### 4.3 Scene / Material / Render (tools present, native verification PENDING)

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

### B1 — Reliability & Lifecycle (PARTIAL)
- Stable `op_id`, mutation lifecycle, timeout uncertainty, reconcile operation, bounded admission queue, timer budget, path containment. Client/heavy-op budgets and async hardening remain open.

### B2 — Modeling Baseline (OPEN)
- Mesh edit mode, vertices/edges/faces, topology edits, extrude/inset/bevel, modifiers, collections, materials. UV unwrap declared unsupported; native acceptance pending.

### B3 — Sculpting Baseline (OPEN)
- Sculpt context validation, mode switching, dynamic topology for Blender 4.5.3, smooth, inflate, grab falloff, symmetry. Brush strokes, masks, face sets and multiresolution declared unsupported; native acceptance pending.

### B4 — Operations & Certification (PENDING)
- Render/export tools present; native Blender 4.5.3 LTS release matrix and exact-HEAD evidence manifest pending (current manifest is historical source `39e2810`).

## 7. Safety / Correctness

- No arbitrary Python execution tool by default.
- Context transitions are explicit and validated.
- Destructive mesh operations are clearly named/documented.
- Long operations have bounded timeout semantics with uncertain receipt generation.
- Topology changes are reported honestly.
- Save/export paths stay inside configured roots (`require_allowed` with `realpath`).

## 8. Completion Gate

- Modeling lane passes end-to-end (OPEN — see 4.1);
- Sculpting lane passes end-to-end (OPEN — see 4.2);
- scene/render baseline works (tools present, verification PENDING);
- capability/context reporting matches runtime (PASS for B0 scope; lifecycle tools `reconcile_operation`/`operation_status` not yet covered in `docs/TOOL_GUIDE.md`);
- SlncTrZ integration checklist passes (PASS for B0 provider-local scope; gateway-side catalog/policy remains an external SlncTrZ-MCP lane item);
- tests cover topology-impacting sculpt/model operations (PENDING — 1630/1630 offline PASS at `f60cf30`, native fixtures pending).
