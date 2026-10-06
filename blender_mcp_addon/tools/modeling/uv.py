# blender_mcp_addon/tools/modeling/uv.py
"""Modeling UV tools — deterministic UV unwrap and smart projection.
Wing: blender | Topic: modeling-uv | Updated: 2026-10-06 15:25
"""

import math

import bpy  # type: ignore

from ...utils import get_object


class ModelingUV:
    """UV unwrapping / projection tools for mesh objects (Blender-native UV ops)."""

    def _uv_stats(self, obj):
        """Deterministic readback snapshot of the mesh's UV data.

        UV data is per-loop (face corner); a healthy unwrap yields at least one
        UV layer with non-zero coordinates. A mesh with no UV layer reports
        zeros so callers can distinguish "no UV data" from "already unwrapped".
        """
        mesh = obj.data
        uv_layers = list(getattr(mesh, "uv_layers", ()) or ())
        if not uv_layers:
            return {"uv_layer_count": 0, "uv_loop_count": 0, "uv_nonzero_loops": 0}

        loop_count = len(uv_layers[0].data)
        nonzero = 0
        for loop_uv in uv_layers[0].data:
            uv = loop_uv.uv
            if uv.x != 0.0 or uv.y != 0.0:
                nonzero += 1
        return {
            "uv_layer_count": len(uv_layers),
            "uv_loop_count": loop_count,
            "uv_nonzero_loops": nonzero,
        }

    def _validate_finite(self, name, value):
        try:
            value = float(value)
        except (TypeError, ValueError):
            return None, f"{name} must be a finite number, got {value!r}."
        if not math.isfinite(value):
            return None, f"{name} must be a finite number, got {value!r}."
        return value, None

    def _restore_context(self, original_active, original_selected):
        try:
            if bpy.context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
        except Exception:
            pass
        try:
            bpy.ops.object.select_all(action="DESELECT")
            for o in original_selected:
                try:
                    o.select_set(True)
                except Exception:
                    pass
            if original_active is not None:
                bpy.context.view_layer.objects.active = original_active
        except Exception:
            pass

    def unwrap_mesh(
        self,
        object_name,
        method="ANGLE_BASED",
        fill_holes=True,
        correct_aspect=True,
        use_subsurf_data=False,
        margin=0.001,
        **kwargs,
    ):
        """Unwrap the whole mesh's UVs using Blender's native unwrap operator."""
        obj = get_object(object_name)
        if obj.type != "MESH":
            return {
                "success": False,
                "error": f"Object '{object_name}' is not a mesh (type: {obj.type}).",
            }

        # H14: validate finite params and enum BEFORE mutating any context.
        if method not in ("ANGLE_BASED", "CONFORMAL"):
            return {
                "success": False,
                "error": f"Invalid method '{method}'. Expected ANGLE_BASED or CONFORMAL.",
            }
        margin, err = self._validate_finite("margin", margin)
        if err:
            return {"success": False, "error": err}

        original_active = bpy.context.view_layer.objects.active
        original_selected = [o for o in bpy.context.selected_objects]

        try:
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.select_all(action="DESELECT")
            obj.select_set(True)
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="SELECT")

            result = bpy.ops.uv.unwrap(
                method=method,
                fill_holes=fill_holes,
                correct_aspect=correct_aspect,
                use_subsurf_data=use_subsurf_data,
                margin=margin,
            )
            bpy.ops.object.mode_set(mode="OBJECT")
            after = self._uv_stats(obj)

            if "FINISHED" not in result:
                return {
                    "success": False,
                    "error": f"UV unwrap operator did not finish: {set(result)}.",
                }
            if after["uv_loop_count"] == 0:
                return {"success": False, "error": "UV unwrap produced no UV data (no UV loops)."}
            if after["uv_nonzero_loops"] == 0:
                return {
                    "success": False,
                    "error": "UV unwrap reported success but produced no non-zero UV coordinates.",
                }

            return {
                "success": True,
                "verified": True,
                "object": object_name,
                "method": method,
                "uv_layer_count": after["uv_layer_count"],
                "uv_loop_count": after["uv_loop_count"],
                "uv_nonzero_loops": after["uv_nonzero_loops"],
                "message": (
                    f"Unwrapped '{object_name}' (method={method}): "
                    f"{after['uv_layer_count']} UV layer(s), {after['uv_loop_count']} UV loops, "
                    f"{after['uv_nonzero_loops']} non-zero."
                ),
            }
        finally:
            self._restore_context(original_active, original_selected)

    def smart_project(
        self,
        object_name,
        angle_limit=66.0,
        island_margin=0.0,
        area_weight=0.0,
        correct_aspect=True,
        scale_to_bounds=False,
        **kwargs,
    ):
        """Project the whole mesh's UVs using Blender's Smart UV Project."""
        obj = get_object(object_name)
        if obj.type != "MESH":
            return {
                "success": False,
                "error": f"Object '{object_name}' is not a mesh (type: {obj.type}).",
            }

        # H14: validate finite params BEFORE mutating any context.
        angle_limit, err = self._validate_finite("angle_limit", angle_limit)
        if err:
            return {"success": False, "error": err}
        island_margin, err = self._validate_finite("island_margin", island_margin)
        if err:
            return {"success": False, "error": err}
        area_weight, err = self._validate_finite("area_weight", area_weight)
        if err:
            return {"success": False, "error": err}

        original_active = bpy.context.view_layer.objects.active
        original_selected = [o for o in bpy.context.selected_objects]

        try:
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.select_all(action="DESELECT")
            obj.select_set(True)
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="SELECT")

            result = bpy.ops.uv.smart_project(
                angle_limit=angle_limit,
                island_margin=island_margin,
                area_weight=area_weight,
                correct_aspect=correct_aspect,
                scale_to_bounds=scale_to_bounds,
            )
            bpy.ops.object.mode_set(mode="OBJECT")
            after = self._uv_stats(obj)

            if "FINISHED" not in result:
                return {
                    "success": False,
                    "error": f"Smart UV Project operator did not finish: {set(result)}.",
                }
            if after["uv_loop_count"] == 0:
                return {
                    "success": False,
                    "error": "Smart UV Project produced no UV data (no UV loops).",
                }
            if after["uv_nonzero_loops"] == 0:
                return {
                    "success": False,
                    "error": (
                        "Smart UV Project reported success but produced no non-zero UV coordinates."
                    ),
                }

            return {
                "success": True,
                "verified": True,
                "object": object_name,
                "angle_limit": angle_limit,
                "uv_layer_count": after["uv_layer_count"],
                "uv_loop_count": after["uv_loop_count"],
                "uv_nonzero_loops": after["uv_nonzero_loops"],
                "message": (
                    f"Smart-projected UVs for '{object_name}' (angle_limit={angle_limit}): "
                    f"{after['uv_layer_count']} UV layer(s), {after['uv_loop_count']} UV loops, "
                    f"{after['uv_nonzero_loops']} non-zero."
                ),
            }
        finally:
            self._restore_context(original_active, original_selected)
