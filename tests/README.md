# Validation

Run commands from the repository root. Offline suites and live Blender scenarios
are separate acceptance lanes.

## Offline CI

```bash
uv sync --group dev
uv run pytest tests/ -q
uv run ruff check blender_mcp_bridge/ tests/ blender_mcp_addon/
uv run ruff format --check blender_mcp_bridge/ tests/ blender_mcp_addon/
uv run mypy blender_mcp_bridge/
uv run python scripts/gen_tools_doc.py
git diff --exit-code -- docs/tools.md
```

CI checks unit behavior, schemas, addon dispatch consistency, the discipline
quarantine, lint, complexity and types. Counts derive from current collection;
offline PASS is not native Blender acceptance.

## Live Blender

Start an accepted Blender version with the addon server enabled, then run the
authenticated bridge. Use an isolated profile and disposable output files.

```bash
uv run python tests/run_integration.py run -s grid --verify
uv run python tests/run_integration.py run -s arch --verify
uv run python tests/run_integration.py run -s print
uv run python tests/run_integration.py run -s filament_tag
```

Only `grid` and `arch` have committed expected snapshots. `print` and
`filament_tag` are smoke scenarios until reviewed baselines are supplied;
`verify -s all` cannot pass with missing expected snapshots.
Legacy architecture/MEP scenarios are test fixtures, not advertised provider
discipline tools.

`--module` is grid-only. `--transport stateful` is the default;
`--transport stateless` exercises the alternate client transport.
Use `approve -s <scenario>` only after reviewing the last-run snapshot;
it records the observed result, including any mistakes.

Record exact source, Blender version/context, outcomes and unresolved findings.
Live scenarios are not run in hosted CI.
