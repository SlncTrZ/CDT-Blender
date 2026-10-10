# CDT-Blender Versioning, Release & Auth-Preserving Deployment

> Project policy · revised 2026-10-10 · stable package 0.2.1

## Three independent identities

- **Package version** uses PEP 440 in `pyproject.toml` and `blender_mcp_bridge/provider_contract.py`. The package release is tagged **`v.<package-version>`**, never inferred from time, an audit tag, or a moving `main` head.
- **MCP contract version** is `cdt-blender-contract-v10` and increments when public tools/schema/capability promises change. It is **not** a package version.
- **Deployment version** is an immutable directory holding the exact release wheel, a pinned workstation agent/addon revision, installed SHA-256 manifest and scoped runtime profile. A release does **not** imply a host is running it.

Sync invariants: package version in `pyproject.toml`, `uv.lock`, and `provider_contract.py` must match; Blender addon numeric `bl_info.version` must match `major.minor.patch`; Git release tag must match the PEP 440 package version. All new release tags are exactly `v.0.x.x`, with three numeric fields and no suffixes. Historic `audit-*` / `freeze/*` tags are evidence/checkpoints and must not trigger publication.

## Release gates

1. Commit a clean source revision; require exact-source CI on `main` and independent Windows native Blender 4.5.3 qualification. No arbitrary `bpy` execution surface.
2. Push the **annotated** version tag to the already-validated commit; GitHub Actions source-release workflow checks exact-source CI and tag/package equality, then attaches a versioned wheel, addon ZIP and SHA-256 manifest. CI must never claim an installed workstation is updated.
3. Build/install to a **new immutable directory**, never overwrite an active venv or addon. Record release tag, full git SHA, contract, artifact hashes and target workstation/Blender build. Verify the installed files with hashes before attaching.
4. Preserve workstation credential source, user auth, and runtime binding. Never rotate or print bearer tokens to deploy code; capture only permission/mode, file hash and a redacted health result. Keep old immutable release and original binding available for rollback.
5. Perform canary health and MCP discovery. Activate the pinned new release only after checks. Changing the workstation agent process mints a *new* runtime generation: an intentional, independently approved restart/rebind must not be mistaken for credential loss.
6. Run authenticated `system_status`, `system_capabilities`, `document_info`, protected root-refusal and one safe addon operation, and compare with baseline. If auth/health is lost, restore the previous pinned registration and profile.
7. Only after deployed checks may a release be labelled production-ready. Windows Blender UI and background are separate qualification scopes; Blender 5.x remains unverified.

## Windows hidden background execution

Do **not** launch long-lived workstation runtime agents through `powershell.exe` in an interactive Scheduled Task: it can leave visible CMD/PowerShell windows. For a background Python agent, schedule `pythonw.exe` directly using `scripts/windows_hidden_agent.pyw` with task setting `Hidden`. That script is not a public MCP tool and uses no console. For headless Blender test rendering, a `pythonw.exe` parent can use Windows `CREATE_NO_WINDOW` and `STARTF_USESHOWWINDOW`/`SW_HIDE`. Always stop and unregister **only uniquely named temporary QA tasks** and verify test ports closed; leave unrelated production tasks and auth agents untouched. A `Hidden` Task Scheduler flag alone does not guarantee a child `powershell.exe` has no visible console.

## Current release-channel labels

- `v.0.2.1`: stable documentation and maintenance release, retains MCP contract v10; production activation remains a separate gate.
- `v.0.2.0`: stable L2 package release; Windows Blender 4.5.3 and offline regressions qualified. This does **not** prove production rollout.
- `v0.2.0rc1`: historical release candidate; do not move or delete its tag.
- `0.1.3+cdt.1`: historical fork metadata used by the old installed v9 provider (keep for rollback).

See `CHANGELOG.md`, `docs/TOOL_GUIDE.md` and private host-specific deployment receipts for evidence.
