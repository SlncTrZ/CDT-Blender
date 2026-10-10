"""Security/refusal coverage for SVG, GPv3, Geometry Nodes and Unicode primitives."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

_DIR = Path(__file__).resolve().parents[1] / "blender_mcp_addon" / "tools"
_VALID_SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 80">'
    b'<rect x="4" y="5" width="110" height="50" fill="#FF0000"/>'
    b"</svg>"
)


def _load(name: str, monkeypatch):
    # Avoid importing the addon server, which requires native Blender's mathutils.
    fake = ModuleType("bpy")
    fake.data = SimpleNamespace(
        objects=SimpleNamespace(get=lambda _: None),
        materials=SimpleNamespace(get=lambda _: None),
        meshes=SimpleNamespace(get=lambda _: None),
        node_groups=SimpleNamespace(get=lambda _: None),
        grease_pencils_v3=SimpleNamespace(get=lambda _: None),
        curves=SimpleNamespace(get=lambda _: None),
    )
    monkeypatch.setitem(sys.modules, "bpy", fake)
    pkg = ModuleType("blender_mcp_addon")
    pkg.__path__ = [str(_DIR.parent)]
    subpkg = ModuleType("blender_mcp_addon.tools")
    subpkg.__path__ = [str(_DIR)]
    monkeypatch.setitem(sys.modules, "blender_mcp_addon", pkg)
    monkeypatch.setitem(sys.modules, "blender_mcp_addon.tools", subpkg)
    spec = importlib.util.spec_from_file_location(
        f"blender_mcp_addon.tools._test_{name}", _DIR / f"{name}.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_svg_baseline_accepts_hex_and_xml_declaration(monkeypatch):
    m = _load("infographic_svg", monkeypatch)
    plain = m.validate_svg_document(_VALID_SVG)
    assert plain["shapes"] == 1
    assert plain["profile"] == "offline-basic-2d"
    declared = b'<?xml version="1.0" encoding="UTF-8"?>\n' + _VALID_SVG
    assert m.validate_svg_document(declared)["shapes"] == 1


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"Z" * (256 * 1024 + 1),
        b'<!DOCTYPE svg [<!ENTITY xx SYSTEM "file:///secret">]>' + _VALID_SVG,
        b'<svg xmlns="http://www.w3.org/2000/svg"><script/></svg>',
        b'<svg xmlns="http://www.w3.org/2000/svg"><foreignObject/></svg>',
        b'<svg xmlns="http://www.w3.org/2000/svg"><rect href="https://example.com" width="1" height="2"/></svg>',
        b'<svg xmlns="http://www.w3.org/2000/svg"><rect fill="url(#external)" width="1" height="2"/></svg>',
        b'<svg xmlns="http://www.w3.org/2000/svg"><style>.x{fill:red}</style><path d="M0 0L1 1"/></svg>',
        b'<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0L1e999 1"/></svg>',
        b'<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0L999999 1"/></svg>',
        b'<svg xmlns="http://www.w3.org/2000/svg"><g /></svg>',
        b'<svg><rect width="1" height="1"/></svg>',
        b'<?xml-stylesheet href="x"?>' + _VALID_SVG,
    ],
    ids=[f"svg-refusal-{index}" for index in range(13)],
)
def test_svg_refuses_external_active_or_oversized_content(monkeypatch, payload):
    m = _load("infographic_svg", monkeypatch)
    with pytest.raises(ValueError):
        m.validate_svg_document(payload)


def test_svg_coordinate_bound_handles_adjacent_commands(monkeypatch):
    m = _load("infographic_svg", monkeypatch)
    payload = _VALID_SVG.replace(b'<rect x="4"', b'<rect x="400000"')
    with pytest.raises(ValueError, match="coordinate"):
        m.validate_svg_document(payload)


def test_gp_points_accepts_xy_and_xyz(monkeypatch):
    m = _load("infographic_grease", monkeypatch)
    assert m._stroke_points([[(0, 1), (2, 3, 4)]]) == [[(0.0, 1.0, 0.0), (2.0, 3.0, 4.0)]]


@pytest.mark.parametrize(
    "strokes",
    [
        [],
        [[]],
        [[(0, 0)]],
        [[(0, 0), (float("nan"), 1)]],
        [[(0, 0), (30000, 1)]],
        [[(0, 0), ("3", 1)]],
        [[(0, 0, 0, 0), (1, 1, 1)]],
        [[(0, 0), (1, 1)]] * 33,
    ],
)
def test_gp_refuses_malformed_points(monkeypatch, strokes):
    m = _load("infographic_grease", monkeypatch)
    with pytest.raises(ValueError):
        m._stroke_points(strokes)


def test_gp_refuses_invalid_frame_budget_before_side_effect(monkeypatch):
    m = _load("infographic_grease", monkeypatch)
    with pytest.raises(ValueError):
        m.create_grease_strokes(
            "Name", strokes=[[(0, 0), (1, 1)]], steps=8, start_frame=1, end_frame=4
        )


_BASE_GN = {
    "name": "DATA",
    "mode": "LINE",
    "count": 18,
    "radius": 0.04,
    "start": (0.0, 0.0, 0.0),
    "end": (2.0, 0.0, 0.0),
    "color": "#12CFFF",
    "frame_start": 1,
    "frame_end": 60,
}


def test_geometry_preset_baseline(monkeypatch):
    m = _load("infographic_geometry", monkeypatch)
    assert m.validate_particle_preset(**_BASE_GN)["rgba"][3] == 1.0


@pytest.mark.parametrize(
    "override",
    [
        {"name": "bad-name!"},
        {"mode": "EXEC"},
        {"count": 10000},
        {"count": True},
        {"radius": -1},
        {"radius": float("inf")},
        {"start": (0, 0)},
        {"end": (0.0, 0.0, 0.0)},
        {"end": (float("nan"), 1, 0)},
        {"color": "red"},
        {"frame_start": 60, "frame_end": 60},
    ],
)
def test_geometry_preset_rejects_bad_inputs(monkeypatch, override):
    m = _load("infographic_geometry", monkeypatch)
    with pytest.raises(ValueError):
        m.validate_particle_preset(**(_BASE_GN | override))


def test_unicode_nfc_vietnamese_and_multiline(monkeypatch):
    m = _load("infographic_unicode", monkeypatch)
    info = m.validate_unicode_text("Tie\u0302\u0301ng Vie\u0323\u0302t\nĐiều khiển AI")
    assert info["normalized_nfc"] is False
    assert info["line_count"] == 2
    assert "Tiếng" in info["text"]
    assert "Việt" in info["text"]


@pytest.mark.parametrize(
    "value",
    ["", "   ", "مرحبا", "שלום", "नमस्ते", "สวัสดี", "A\u202eB", "A\u200dB", "a\x00b"],
)
def test_unicode_refuses_complex_shaping_controls(monkeypatch, value):
    m = _load("infographic_unicode", monkeypatch)
    with pytest.raises(ValueError):
        m.validate_unicode_text(value)
