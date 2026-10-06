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
> Status: **B0 baseline/context PASS** · Verified native baseline is **Blender 4.5.3 LTS / Windows 11**; other Blender versions/platforms remain **unverified** · Spec pin: `CDT_Engineer@643019c`
>
> **CDT certified host target:** Blender **4.5.3 LTS on Windows 11**.
> Current acceptance and quality scoring are bound to this target only. Other
> Blender versions/platforms are optional future compatibility lanes; they are
> not implied supported today and do not reduce the current target's score.

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

Current verified checkpoint (certified-at: 2026-09-14 native evidence): **B0 baseline/context is accepted** on Blender 4.5.3 LTS / Windows 11. Native evidence covers background discovery plus live UI with no active object, OBJECT, EDIT_MESH and SCULPT contexts; authenticated Streamable HTTP MCP discovery/status/capabilities and cube create → `object_get` read-back are accepted end-to-end. The addon metadata minimum is 4.5.3, while later Blender versions and non-Windows platforms remain unverified rather than implicitly supported. B1 reliability is partial, B2 modeling / B3 sculpting remain open mandatory gates (UV unwrap, brush strokes, masks, face sets, multiresolution declared unsupported), and B4 certification is pending — see `docs/ROADMAP.md`. This B0 checkpoint does **not** mean the provider is complete: Modeling and Sculpting remain mandatory end-to-end lanes.

## Start here

1. Read `docs/SPEC_BASELINE.md` and `docs/ROADMAP.md`.
2. Read `specs/MCP_PROVIDER_STANDARD.md`, `specs/ARCHITECTURE.md` and `specs/CONTRACTS.md`.
3. Read `docs/TOOL_GUIDE.md` and `docs/SLNCTRZ_INTEGRATION.md`.
4. Research current `bpy` context behavior before changing the bridge boundary.

Agent-local working instructions are supplied by the execution environment and are intentionally not part of the public repository. External research provenance is recorded in `ATTRIBUTION.md`.

## Gateway-controlled execution lifecycle

Integration target: an authorized lifecycle controller ensures the native runtime, verifies readiness, syncs the already-registered gateway provider, verifies activation, and refreshes client tools/list. The lifecycle tools are not implemented or advertised by this provider merely because this guide exists. A stopped engine must not be the only endpoint capable of starting itself.

Require the accepted Blender 4.5.3 LTS Windows context, authenticated façade and connected addon. Verify mode/context separately from provider liveness. Bounded addon admission/tick budgets and timeout reconciliation remain rollout gates; B0 does not certify complete Modeling/Sculpting.

Stop/drain requires verified ownership, no unresolved mutation and explicit dirty-document handling. Do not kill all application processes or silently discard work. Gateway hot activation does not require a gateway restart and may change the provider generation.

Interface reference: [CDT_Engineer Execution Lifecycle Contract](https://github.com/SlncTrZ/CDT_Engineer/blob/main/docs/EXECUTION_LIFECYCLE_CONTRACT.md). The contract is a draft target and is not published by this documentation-only workspace update; it is available in the sibling CDT_Engineer checkout. Existing pinned `specs/**` remain unchanged.
