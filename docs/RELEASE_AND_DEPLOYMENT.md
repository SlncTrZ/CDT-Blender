# CDT-Blender — Release and deployment

**Release:** `0.2.2` · tag `v.0.2.2` · MCP contract `cdt-blender-contract-v10` · 121 tools.

The [release page](https://github.com/SlncTrZ/CDT-Blender/releases) is the source of versioned artifacts. The release workflow produces a bridge wheel, Blender addon ZIP and `SHA256SUMS`. Verify both artifact hashes before installation; source and runtime versions are distinct.

## Install and connect

1. Select the matching stable release. Check its declared Python requirements and native Blender target. The accepted native target is **Blender 4.5.3 LTS on Windows 11**. Later Blender versions are not certified by a minimum-version field.
2. Install the wheel into a **new** isolated Python environment. Install the matching addon ZIP in Blender's intended user profile and start its localhost-only socket from the intended UI session. Do not replace a currently open scene or install a test addon over an active runtime.
3. Start the bridge with the [Gateway configuration](SLNCTRZ_INTEGRATION.md). Use managed authentication (`BLENDER_MCP_TOKEN` for direct HTTP, or the workstation's owner-managed credential pipe/profile for the separated Gateway-agent topology). Do not copy bearer tokens between hosts or echo them in logs.
4. Before editing, call `help`, `system_status`, `system_capabilities`, `document_info` and confirm **running** contract `v10`, 121 tools, addon connection, correct scene, active mode and writable roots. Treat a disconnected addon as an unavailable native session, not as lost auth.

## Managed `.227` deployment

The managed service is `cdt-blender.service`, using the published `0.2.1` wheel verified against release `SHA256SUMS`, with authenticated Streamable HTTP at `http://127.0.0.1:8812/mcp`. Gateway-adapter acceptance discovers 121 tools with zero normalized drift. Native addon connectivity remains a separate dependency and must be checked before Blender edits.

## Stage, promote, rollback

Keep installed builds and their SHA manifests immutable. Verify a new agent's runtime generation against its bound profile before switching an owner-managed Gateway registration. Perform one disposable scene operation, save/reopen, check a failed outside-root request and compare authentication/credential-store state before and after. Roll back registration, addon and agent **together** on failure, preserving the user's scene and broker credentials.

The historical `0.2.0rc1` artifact and old Gateway v9 registration are rollback/evidence identities only. The `0.2.1` service is installed independently on `.227` and live Gateway routing is active over authenticated Streamable HTTP. Native Blender/addon readiness must still be verified separately before edits.

[Native tool contract](TOOL_GUIDE.md) · [Versioning policy](VERSIONING.md) · [Integration](SLNCTRZ_INTEGRATION.md) · [Validation](../tests/README.md).
