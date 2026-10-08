# Test layout

- `test_tool_schemas.py` — bridge/advertised-tool consistency (110 advertised MCP tools: 108 covered by `docs/tools.md` categories + 2 lifecycle tools `reconcile_operation`/`operation_status`; 8 quarantined discipline handlers held out — see `scripts/gen_tools_doc.py`; counts verified 2026-10-06 at `f60cf30`).
- `test_sessions.py`, `test_design_rules.py` — session playback and local advisory lookups (no Blender needed).
- `run_integration.py`, `scenarios/`, `benchmarks/` — live-Blender gates; need a running Blender with the addon started. Not run in CI.
- Capability/context honesty and topology-impact fixtures for modeling/sculpting land with the B1/B2 lanes.
