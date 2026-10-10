# CDT-Blender

Blender-native MCP provider for bounded 3D execution. The bridge and addon own
native operations; engineering-domain rules belong to CDT_Engineer.

CDT package version `0.2.1` (MCP contract `cdt-blender-contract-v10`);
upstream fork baseline `0.1.3`. Verified native baseline: Blender 4.5.3 LTS on
Windows 11. Other versions/platforms are unverified. Modeling/sculpt support is
tool-specific; context acceptance is not complete modeling/sculpt certification.

## Start

```bash
uv sync --group dev
uv run cdt-blender serve --host 127.0.0.1 --port 8008
```

Provision `BLENDER_MCP_TOKEN` through the deployment environment or secret
manager before serving. In Blender, enable `blender_mcp_addon` and start its MCP
server. Keep the addon socket local to the workstation.

The bridge exposes authenticated Streamable HTTP and unauthenticated health
liveness. A healthy bridge does not prove the addon or required UI mode is ready.

## Use

Call `help`, `system_status` and `system_capabilities` first. Verify the current
application version, active object and mode for each operation. The runtime guide
is the contract; pin its `contract_hash`. Reconcile uncertain mutation outcomes
before retrying; timeout does not prove cancellation.

- [Runtime tool contract](docs/TOOL_GUIDE.md).
- [Generated tool reference](docs/tools.md).
- [Gateway integration and operation](docs/SLNCTRZ_INTEGRATION.md).
- [Release, installation and rollback](docs/RELEASE_AND_DEPLOYMENT.md).
- [Contributor validation](tests/README.md).
- [Pinned shared specs](docs/SPEC_BASELINE.md).
- [Version tags, release artifacts and credential-safe deployment](docs/VERSIONING.md).

## Attribution

MIT fork of [seehiong/blender-mcp-bridge](https://github.com/seehiong/blender-mcp-bridge),
pinned at `b8113ae` (v0.1.3). See [LICENSE](LICENSE) and [ATTRIBUTION](ATTRIBUTION.md).
