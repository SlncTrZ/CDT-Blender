# Test layout

- `test_tool_schemas.py` — bridge/advertised-tool consistency (95 tools; quarantine enforced).
- `test_sessions.py`, `test_design_rules.py` — session playback and local advisory lookups (no Blender needed).
- `run_integration.py`, `scenarios/`, `benchmarks/` — live-Blender gates; need a running Blender with the addon started. Not run in CI.
- Capability/context honesty and topology-impact fixtures for modeling/sculpting land with the B1/B2 lanes.
