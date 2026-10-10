"""Version pin consistency: package metadata, lockfile, addon and contract."""

from __future__ import annotations

import ast
import re
import tomllib
from pathlib import Path

from blender_mcp_bridge import provider_contract as contract

ROOT = Path(__file__).resolve().parents[1]


def test_provider_package_version_matches_source_and_lockfile():
    pkg = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    assert pkg == contract.PROVIDER_VERSION
    lock = tomllib.loads((ROOT / "uv.lock").read_text())
    entry = next(p for p in lock["package"] if p["name"] == "cdt-blender")
    assert entry["version"] == pkg
    assert re.fullmatch(r"0\.\d+\.\d+", pkg)


def test_addon_major_minor_patch_matches_provider_release():
    addon = ast.parse((ROOT / "blender_mcp_addon/__init__.py").read_text())
    info = next(
        stmt.value
        for stmt in addon.body
        if isinstance(stmt, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "bl_info" for target in stmt.targets)
    )
    values = {
        x.value: y
        for x, y in zip(info.keys, info.values, strict=True)
        if isinstance(x, ast.Constant)
    }
    addon_version = ast.literal_eval(values["version"])
    stem = re.match(r"^(\d+)\.(\d+)\.(\d+)", contract.PROVIDER_VERSION)
    assert stem is not None
    assert addon_version == tuple(map(int, stem.groups()))


def test_release_workflow_uses_semantic_tags_not_audit_tags():
    workflow = (ROOT / ".github/workflows/publish-release.yml").read_text()
    assert 'tags: ["v.0.*.*"]' in workflow
    assert 'tag != f"v.{version}"' in workflow
    assert "--verify-tag" in workflow
    assert "SHA256SUMS" in workflow


def test_windows_qa_agent_launcher_uses_console_free_python():
    script = (ROOT / "scripts/windows_hidden_agent.pyw").read_text()
    assert "runtime_cli" in script
    assert "runpy.run_module" in script
    assert "subprocess." not in script
