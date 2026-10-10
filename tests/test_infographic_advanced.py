"""Input safety tests for advanced infographic primitives without native Blender."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


def load(monkeypatch):
    fake_bpy = ModuleType("bpy")
    fake_bpy.data = SimpleNamespace(materials=SimpleNamespace(get=lambda _: None))
    monkeypatch.setitem(sys.modules, "bpy", fake_bpy)
    directory = Path(__file__).resolve().parents[1] / "blender_mcp_addon" / "tools"
    package = ModuleType("blender_mcp_addon")
    package.__path__ = [str(directory.parent)]
    tools_package = ModuleType("blender_mcp_addon.tools")
    tools_package.__path__ = [str(directory)]
    monkeypatch.setitem(sys.modules, "blender_mcp_addon", package)
    monkeypatch.setitem(sys.modules, "blender_mcp_addon.tools", tools_package)
    path = directory / "infographic_advanced.py"
    spec = importlib.util.spec_from_file_location("blender_mcp_addon.tools._test_advanced", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_tokenization(monkeypatch):
    m = load(monkeypatch)
    assert m._tokens("Hello  world", "word") == ["Hello", "  ", "world"]
    assert m._tokens("one\ntwo", "line") == ["one\n", "two"]
    with pytest.raises(ValueError):
        m._tokens("test", "glyph")


@pytest.mark.parametrize("value", [float("nan"), float("inf"), True, "4", -1, 100])
def test_numeric_validation(monkeypatch, value):
    m = load(monkeypatch)
    with pytest.raises(ValueError):
        m._finite(value, 0, 10, "test")


@pytest.mark.parametrize(
    "params",
    [
        {"text": "", "prefix": "A", "mode": "word", "start_frame": 1},
        {"text": "hi", "prefix": "A", "mode": "word", "start_frame": 0},
        {"text": "hi", "prefix": "A", "mode": "line", "start_frame": 1, "duration": 0},
        {"text": "hi", "prefix": "A", "mode": "word", "start_frame": 1, "color": "bad"},
        {"text": "hi", "prefix": "A", "mode": "word", "start_frame": 1, "location": (1, 2)},
    ],
)
def test_invalid_text_group_refusal(monkeypatch, params):
    m = load(monkeypatch)
    with pytest.raises(ValueError):
        m.animate_text_groups(**params)


def test_invalid_gradient_refusal(monkeypatch):
    m = load(monkeypatch)
    for stops in (
        [],
        [{"position": 0, "color": "#000000"}],
        [{"position": 0, "color": "#000000"}, {"position": 0, "color": "#FFFFFF"}],
        [{"position": 0, "color": "#000000"}, {"position": 1, "color": "bad"}],
    ):
        with pytest.raises(ValueError):
            m.gradient_with_stops("G", stops=stops)
