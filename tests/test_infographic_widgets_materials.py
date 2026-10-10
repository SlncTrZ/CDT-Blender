"""Input-boundary regression tests for internal material and chart primitives."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


def _load(monkeypatch, name):
    directory = Path(__file__).resolve().parents[1] / "blender_mcp_addon" / "tools"
    fake_bpy = ModuleType("bpy")
    fake_bpy.data = SimpleNamespace(
        materials=SimpleNamespace(get=lambda _: None),
        objects=SimpleNamespace(get=lambda _: None),
        curves=SimpleNamespace(get=lambda _: None),
        meshes=SimpleNamespace(get=lambda _: None),
    )
    monkeypatch.setitem(sys.modules, "bpy", fake_bpy)
    package = ModuleType("blender_mcp_addon")
    package.__path__ = [str(directory.parent)]
    tools_package = ModuleType("blender_mcp_addon.tools")
    tools_package.__path__ = [str(directory)]
    monkeypatch.setitem(sys.modules, "blender_mcp_addon", package)
    monkeypatch.setitem(sys.modules, "blender_mcp_addon.tools", tools_package)
    spec = importlib.util.spec_from_file_location(
        f"blender_mcp_addon.tools._test_{name}", directory / f"{name}.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "key,value",
    [
        ("roughness", -0.1),
        ("ior", 4),
        ("alpha", float("nan")),
        ("metallic", True),
        ("emission_strength", 101),
        ("unbounded", 1),
    ],
)
def test_material_rejects_bad_scalars(monkeypatch, key, value):
    m = _load(monkeypatch, "infographic_materials")
    with pytest.raises(ValueError):
        m._validate_scalar(key, value)


@pytest.mark.parametrize(
    "values,colors",
    [
        ([], []),
        ([0], ["#FFFFFF"]),
        ([1, 2], ["#FFFFFF"]),
        ([float("inf")], ["#FFFFFF"]),
        ([1], ["#NOPE00"]),
        ([1] * 25, ["#FFFFFF"] * 25),
    ],
)
def test_chart_rejects_invalid_inputs_before_mutation(monkeypatch, values, colors):
    m = _load(monkeypatch, "infographic_widgets")
    with pytest.raises(ValueError):
        m.create_bar_chart(prefix="T", values=values, colors=colors)


@pytest.mark.parametrize(
    "progress,interval",
    [
        (-0.1, (1, 10)),
        (1.1, (1, 10)),
        (float("nan"), (1, 10)),
        (0.5, (10, 10)),
    ],
)
def test_arc_rejects_invalid_progress(monkeypatch, progress, interval):
    m = _load(monkeypatch, "infographic_widgets")
    with pytest.raises(ValueError):
        m.create_progress_arc(
            name="T", progress=progress, start_frame=interval[0], end_frame=interval[1]
        )


@pytest.mark.parametrize(
    "threshold,quality",
    [
        (float("nan"), "HIGH"),
        (-1, "HIGH"),
        (101, "HIGH"),
        (1, "ULTRA"),
        (True, "HIGH"),
    ],
)
def test_glow_refuses_invalid_inputs(monkeypatch, threshold, quality):
    m = _load(monkeypatch, "infographic_fx")
    with pytest.raises(ValueError):
        m.configure_glow(threshold=threshold, quality=quality)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"text": "Hello", "prefix": "T", "start_frame": 1, "frames_per_character": 0},
        {"text": "", "prefix": "T", "start_frame": 1},
        {"text": "Hello", "prefix": "T", "start_frame": 0},
        {"text": "Hello", "prefix": "T", "start_frame": 1, "frames_per_character": 121},
    ],
)
def test_typewriter_rejects_invalid_requests(monkeypatch, kwargs):
    m = _load(monkeypatch, "infographic_typography")
    with pytest.raises(ValueError):
        m.animate_typewriter(**kwargs)


def test_shared_material_refused_before_changes(monkeypatch):
    m = _load(monkeypatch, "infographic_materials")
    fake = SimpleNamespace(name="shared", users=2)
    monkeypatch.setattr(m, "_bsdf", lambda _: (fake, None))
    with pytest.raises(ValueError, match="Shared material"):
        m.update_material("shared", scalars={"roughness": 0.2})
    with pytest.raises(ValueError, match="Shared material"):
        m.animate_material_property(
            "shared",
            property_name="alpha",
            keyframes=[
                {"frame": 1, "value": 0},
                {"frame": 2, "value": 1},
            ],
        )


def test_glow_refuses_existing_node_graph(monkeypatch):
    m = _load(monkeypatch, "infographic_fx")
    m.bpy.context = SimpleNamespace(
        scene=SimpleNamespace(
            use_nodes=True,
            node_tree=SimpleNamespace(nodes=[object()]),
        )
    )
    with pytest.raises(ValueError, match="refusing destructive rewrite"):
        m.configure_glow(threshold=1, quality="HIGH")


def test_material_refuses_missing_material(monkeypatch):
    m = _load(monkeypatch, "infographic_materials")
    with pytest.raises(ValueError, match="Existing node material"):
        m.update_material("missing", scalars={"roughness": 0.5})
    with pytest.raises(ValueError, match="Existing node material"):
        m.animate_material_property(
            "missing",
            property_name="alpha",
            keyframes=[
                {"frame": 1, "value": 0},
                {"frame": 10, "value": 1},
            ],
        )
