"""Pure validation tests for internal infographic primitives without Blender runtime."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest


def load_module(monkeypatch):
    monkeypatch.setitem(sys.modules, "bpy", ModuleType("bpy"))
    path = (
        Path(__file__).resolve().parents[1]
        / "blender_mcp_addon"
        / "tools"
        / "infographic_native.py"
    )
    spec = importlib.util.spec_from_file_location("_test_infographic_native", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_unicode_combining_and_zwj_groups(monkeypatch):
    m = load_module(monkeypatch)
    assert m._graphemes("A\u0301B") == ["A\u0301", "B"]
    assert m._graphemes("X\u200dY") == ["X\u200dY"]


def test_color_validation(monkeypatch):
    m = load_module(monkeypatch)
    assert m._hex_rgba("#FF0080") == (1.0, 0.0, 128 / 255, 1.0)
    for value in ("red", "#GG0000", "#FFFF", "", None):
        with pytest.raises(ValueError):
            m._hex_rgba(value)


@pytest.mark.parametrize(
    "params",
    [
        {"text": "", "prefix": "a", "start_frame": 1},
        {"text": "a", "prefix": "", "start_frame": 1},
        {"text": "a", "prefix": "a", "start_frame": 0},
        {"text": "a", "prefix": "a", "start_frame": 1, "duration": 0},
        {"text": "a", "prefix": "a", "start_frame": 1, "tracking": -1},
        {"text": "a", "prefix": "a", "start_frame": 1, "color": "#xyzxyz"},
    ],
)
def test_rejects_invalid_glyph_requests_before_side_effects(monkeypatch, params):
    m = load_module(monkeypatch)
    with pytest.raises(ValueError):
        m.animate_characters(**params)


def test_gradient_refuses_invalid_colors_before_side_effects(monkeypatch):
    m = load_module(monkeypatch)
    with pytest.raises(ValueError):
        m.configure_gradient_material("test", start_color="#nope", end_color="#000000")
