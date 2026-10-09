"""Named mesh edits must leave other selected meshes unchanged."""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest


class MeshObject:
    def __init__(self, name, selected):
        self.name = name
        self.type = "MESH"
        self.selected = selected
        self.data = types.SimpleNamespace(
            vertices=[None] * 8,
            polygons=[types.SimpleNamespace(select=True) for _ in range(6)],
            update=lambda: None,
        )

    def select_set(self, value):
        self.selected = value


class EditContext:
    def __init__(self, objects):
        self.objects = objects
        self.mode = "OBJECT"
        self.view_layer = types.SimpleNamespace(objects=types.SimpleNamespace(active=objects[-1]))
        self.tool_settings = types.SimpleNamespace(mesh_select_mode=(False, False, True))

    @property
    def selected_objects(self):
        return [obj for obj in self.objects if obj.selected]


@pytest.mark.parametrize("method", ["extrude_mesh", "inset_faces"])
@pytest.mark.parametrize("target_selected", [True, False])
def test_named_edit_isolates_target_and_restores_original_selection(
    monkeypatch, method, target_selected
):
    target = MeshObject("target", target_selected)
    neighbor = MeshObject("neighbor", True)
    context = EditContext([target, neighbor])
    edit_targets = []

    def mode_set(*, mode):
        context.mode = "EDIT_MESH" if mode == "EDIT" else mode
        if mode == "EDIT":
            edit_targets[:] = context.selected_objects
        return {"FINISHED"}

    def select_all(*, action):
        assert action == "DESELECT"
        for obj in context.objects:
            obj.select_set(False)

    def edit(**kwargs):
        for obj in edit_targets:
            obj.data.vertices.extend([None] * 4)
            obj.data.polygons.extend([types.SimpleNamespace(select=True)] * 4)
        return {"FINISHED"}

    bpy = types.SimpleNamespace(
        context=context,
        ops=types.SimpleNamespace(
            object=types.SimpleNamespace(mode_set=mode_set, select_all=select_all),
            mesh=types.SimpleNamespace(extrude_region_move=edit, inset=edit),
        ),
    )
    utils = types.ModuleType("blender_mcp_addon.utils")
    utils.get_object = lambda name: target
    utils.get_collection = lambda name: None
    monkeypatch.setitem(sys.modules, "bpy", bpy)
    monkeypatch.setitem(sys.modules, "blender_mcp_addon.utils", utils)
    source = Path(__file__).resolve().parents[1] / "blender_mcp_addon/tools/modeling/operators.py"
    namespace = {"__package__": "blender_mcp_addon.tools.modeling"}
    exec(compile(source.read_text(), str(source), "exec"), namespace)
    tools = namespace["ModelingOperators"]()
    kwargs = {"move": [0, 0, 1]} if method == "extrude_mesh" else {"thickness": 0.1}

    result = getattr(tools, method)("target", **kwargs)

    assert result["success"] is True
    assert edit_targets == [target]
    assert len(target.data.vertices) == 12
    assert len(neighbor.data.vertices) == 8
    assert len(neighbor.data.polygons) == 6
    assert context.mode == "OBJECT"
    assert target.selected is target_selected
    assert neighbor.selected is True
    assert context.view_layer.objects.active is neighbor
