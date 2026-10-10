"""Provider L2 infographic schema, dispatcher, refusal and security regression.

Tests are host-independent; Windows Blender native addon-dispatch fixtures
provide separate proof that the real handlers run on Blender 4.5.3 LTS.
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from blender_mcp_bridge.tools import get_mcp_tools
from blender_mcp_bridge.tools.infographic import get_infographic_tools

ROOT = Path(__file__).resolve().parents[1]
EXPORTED = {
    "import_svg_curves",
    "create_grease_strokes",
    "create_filled_grease_tween",
    "create_particle_preset",
    "create_animated_particle_grid",
    "create_unicode_text",
    "create_shaped_text_plane",
}


def test_public_tools_are_unique_and_mutation_receipted():
    all_tools = get_mcp_tools()
    names = [tool.name for tool in all_tools]
    assert len(names) == len(set(names))
    assert EXPORTED <= set(names)
    for tool in all_tools:
        if tool.name in EXPORTED:
            assert tool.inputSchema.get("additionalProperties") is False
            assert "op_id" in tool.inputSchema["properties"]
            assert "op_id" not in tool.inputSchema["required"]


def test_schema_and_addon_server_dispatch_are_consistent():
    addon_ast = ast.parse((ROOT / "blender_mcp_addon/tools/infographic_tools.py").read_text())
    server = (ROOT / "blender_mcp_addon/server.py").read_text()
    classes = [node for node in addon_ast.body if isinstance(node, ast.ClassDef)]
    mixins = {node.name for node in classes}
    assert "InfographicTools" in mixins
    methods = {
        node.name
        for node in classes
        if node.name == "InfographicTools"
        for node in node.body
        if isinstance(node, ast.FunctionDef)
    }
    assert EXPORTED == methods
    assert "    InfographicTools," in server
    for name in EXPORTED:
        assert f'"{name}": self.{name}' in server


def test_root_sensitive_operations_are_guarded_by_bridge_and_addon():
    bridge = (ROOT / "blender_mcp_bridge/server.py").read_text()
    addon = (ROOT / "blender_mcp_addon/tools/infographic_tools.py").read_text()
    for name in ("import_svg_curves", "create_unicode_text", "create_shaped_text_plane"):
        assert f'        "{name}",' in bridge
        assert f"def {name}(" in addon
    assert "allow_roots=_allow_roots or []" in addon


def _load(name: str, monkeypatch):
    directory = ROOT / "blender_mcp_addon/tools"
    fake = ModuleType("bpy")
    fake.data = SimpleNamespace(
        objects=SimpleNamespace(get=lambda _: None),
        materials=SimpleNamespace(get=lambda _: None),
        node_groups=SimpleNamespace(get=lambda _: None),
        meshes=SimpleNamespace(get=lambda _: None),
        grease_pencils_v3=SimpleNamespace(get=lambda _: None),
    )
    monkeypatch.setitem(sys.modules, "bpy", fake)
    pkg = ModuleType("blender_mcp_addon")
    pkg.__path__ = [str(directory.parent)]
    sub = ModuleType("blender_mcp_addon.tools")
    sub.__path__ = [str(directory)]
    monkeypatch.setitem(sys.modules, "blender_mcp_addon", pkg)
    monkeypatch.setitem(sys.modules, "blender_mcp_addon.tools", sub)
    spec = importlib.util.spec_from_file_location(
        f"blender_mcp_addon.tools._test_{name}", directory / f"{name}.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "style",
    [
        "fill:#24B9EF;stroke:#B47EFF;stroke-width:2;opacity:0.6",
        "fill:#CCC;stroke:none;fill-rule:evenodd",
        "stroke:#ABCDEF;stroke-linecap:round;stroke-linejoin:bevel",
    ],
)
def test_svg_safe_inline_styles(monkeypatch, style):
    mod = _load("infographic_svg", monkeypatch)
    text = f'<svg xmlns="http://www.w3.org/2000/svg"><circle cx="4" cy="5" r="3" style="{style}"/></svg>'
    assert mod.validate_svg_document(text.encode())["shapes"] == 1


@pytest.mark.parametrize(
    "style",
    [
        "fill:url(#id)",
        "fill:javascript:alert(1)",
        "behavior:expression(a)",
        "background-image:http://domain/x",
        "fill:#ZZZ",
        "stroke-width:999999",
        "opacity:-1",
        "fill:red",
        "fill:#FFF;stroke:currentColor",
        "fill:#ABC;stroke:#123;animation-name:a",
    ],
)
def test_svg_rejects_active_or_unsupported_inline_styles(monkeypatch, style):
    mod = _load("infographic_svg", monkeypatch)
    text = f'<svg xmlns="http://www.w3.org/2000/svg"><rect width="3" height="3" style="{style}"/></svg>'
    with pytest.raises(ValueError):
        mod.validate_svg_document(text.encode())


def test_grease_tween_requires_matching_topology(monkeypatch):
    mod = _load("infographic_grease_tween", monkeypatch)
    source = [[(0, 0), (1, 0), (1, 1)]]
    target = [[(0, 0), (1, 0), (1, 1)]]
    result = mod._validate_morph(source, target, 12)
    assert len(result[0][0]) == 3
    with pytest.raises(ValueError, match="identical"):
        mod._validate_morph(source, [[(0, 0), (1, 1)]], 12)
    with pytest.raises(ValueError, match="2..32"):
        mod._validate_morph(source, target, 500)


@pytest.mark.parametrize(
    "params",
    [
        {"rows": 40, "columns": 40},
        {"rows": 1, "columns": 3},
        {"rows": 4, "columns": 4, "amplitude": float("nan")},
        {"rows": 4, "columns": 4, "particle_radius": -1},
        {"rows": 4, "columns": 4, "color": "red"},
        {"rows": 4, "columns": 4, "start_frame": 10, "end_frame": 1},
    ],
)
def test_grid_refuses_unsafe_requests(monkeypatch, params):
    mod = _load("infographic_geometry_grid", monkeypatch)
    base = dict(
        name="Grid",
        rows=8,
        columns=8,
        spacing=0.25,
        amplitude=0.1,
        particle_radius=0.035,
        start_frame=1,
        end_frame=60,
        color="#44FFEE",
    )
    with pytest.raises(ValueError):
        mod.validate_grid_preset(**(base | params))


def test_shaped_text_asset_path_boundaries(tmp_path):
    script = ROOT / "scripts/infographic_shape_text_asset.py"
    spec = importlib.util.spec_from_file_location("test_shaper", script)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    root = tmp_path / "root"
    root.mkdir()
    font = root / "allowed.ttf"
    font.write_bytes(b"F" * 1200)
    other = tmp_path / "other"
    other.mkdir()
    with pytest.raises(ValueError, match="allowed root"):
        mod.validate_request(
            "مرحبا",
            direction="rtl",
            language="ar",
            font_size=66,
            font_path=font,
            output=other / "bad.png",
            allow_roots=[root],
        )
    with pytest.raises(ValueError, match="Language unsupported"):
        mod.validate_request(
            "test",
            direction="ltr",
            language="xx",
            font_size=66,
            font_path=font,
            output=root / "ok.png",
            allow_roots=[root],
        )
    valid = mod.validate_request(
        "مرحبا",
        direction="rtl",
        language="ar",
        font_size=66,
        font_path=font,
        output=root / "ok.png",
        allow_roots=[root],
    )
    assert valid["destination"] == root / "ok.png"


def test_all_new_schemas_have_bounded_inputs():
    tools = get_infographic_tools()
    assert len(tools) == 7
    for tool in tools:
        assert tool.inputSchema["required"]
        assert "op_id" not in tool.inputSchema["properties"]
        assert tool.inputSchema["additionalProperties"] is False
