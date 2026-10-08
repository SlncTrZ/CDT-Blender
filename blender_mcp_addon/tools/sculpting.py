# blender_mcp_addon/tools/sculpting.py

import bmesh  # type: ignore
import bpy  # type: ignore
from mathutils import Vector  # type: ignore

from ..utils import get_object


class SculptingTools:
    """Tools for mesh sculpting operations in Blender."""

    def enter_sculpt_mode(self, object_name):
        """Switch a mesh object into Sculpt Mode."""
        obj = get_object(object_name)
        if obj.type != "MESH":
            return {
                "success": False,
                "error": f"Object '{object_name}' is not a mesh (type: {obj.type}).",
            }

        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode="SCULPT")

        return {
            "success": True,
            "message": f"Object '{object_name}' is now in Sculpt Mode.",
        }

    def exit_sculpt_mode(self):
        """Return from Sculpt Mode (or any mode) back to Object Mode."""
        if bpy.context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        return {"success": True, "message": "Returned to Object Mode."}

    def set_dyntopo(self, enabled=True, detail_size=12, constant_detail=False, detail_range=0.35):
        """Enable or disable Dynamic Topology in Sculpt Mode.

        Must already be in Sculpt Mode (call enter_sculpt_mode first).
        Dynamic Topology automatically subdivides polygons as you sculpt
        to allow infinite resolution detail in specific areas.
        """
        if bpy.context.mode != "SCULPT":
            return {
                "success": False,
                "error": "Must be in Sculpt Mode to configure Dyntopo. Call enter_sculpt_mode first.",
            }

        obj = bpy.context.active_object
        currently_enabled = getattr(obj, "use_dynamic_topology_sculpting", False)

        if enabled and not currently_enabled:
            bpy.ops.sculpt.dynamic_topology_toggle()
        elif not enabled and currently_enabled:
            bpy.ops.sculpt.dynamic_topology_toggle()

        sculpt = bpy.context.scene.tool_settings.sculpt
        if hasattr(sculpt, "detail_size"):
            sculpt.detail_size = detail_size
        if hasattr(sculpt, "detail_type_method"):
            sculpt.detail_type_method = "CONSTANT" if constant_detail else "RELATIVE"

        return {
            "success": True,
            "enabled": enabled,
            "detail_size": detail_size,
            "message": f"Dynamic Topology {'enabled' if enabled else 'disabled'} (detail_size={detail_size}).",
        }

    def apply_sculpt_smooth(self, object_name, iterations=3, factor=0.5):
        """Apply Laplacian smoothing to a mesh via BMesh.

        Rounds out hard edges and bumps across the whole surface.
        Works in Object Mode without requiring a live viewport context.
        """
        obj = get_object(object_name)
        if obj.type != "MESH":
            return {"success": False, "error": f"'{object_name}' is not a mesh."}

        # Ensure Object Mode for BMesh edit
        original_mode = bpy.context.mode
        original_active = bpy.context.view_layer.objects.active
        bpy.context.view_layer.objects.active = obj
        if original_mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")

        bm = bmesh.new()
        bm.from_mesh(obj.data)

        for _ in range(iterations):
            bmesh.ops.smooth_vert(
                bm,
                verts=bm.verts,
                factor=factor,
                mirror_clip_x=False,
                mirror_clip_y=False,
                mirror_clip_z=False,
                clip_dist=0.0,
                use_axis_x=True,
                use_axis_y=True,
                use_axis_z=True,
            )

        bm.to_mesh(obj.data)
        obj.data.update()
        bm.free()

        bpy.context.view_layer.objects.active = original_active

        return {
            "success": True,
            "iterations": iterations,
            "factor": factor,
            "message": f"Applied {iterations} smooth pass(es) with factor={factor} to '{object_name}'.",
        }

    def sculpt_inflate(self, object_name, distance=0.05, mask_below_z=None):
        """Inflate or deflate a mesh by displacing vertices along their normals.

        Positive distance = balloon/puff effect (expand outward).
        Negative distance = shrink inward.
        Use mask_below_z to protect the flat base of a model (e.g. mask_below_z=0.0).
        mask_below_z is in WORLD space, matching the object's Location Z in the UI.
        """
        obj = get_object(object_name)
        if obj.type != "MESH":
            return {"success": False, "error": f"'{object_name}' is not a mesh."}

        original_active = bpy.context.view_layer.objects.active
        bpy.context.view_layer.objects.active = obj
        if bpy.context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")

        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.normal_update()

        world_matrix = obj.matrix_world

        affected = 0
        for vert in bm.verts:
            if mask_below_z is not None and (world_matrix @ vert.co).z < mask_below_z:
                continue
            vert.co += vert.normal * distance
            affected += 1

        bm.to_mesh(obj.data)
        obj.data.update()
        bm.free()

        bpy.context.view_layer.objects.active = original_active

        return {
            "success": True,
            "affected_vertices": affected,
            "distance": distance,
            "message": f"Inflated '{object_name}' by {distance} along vertex normals ({affected} vertices).",
        }

    def sculpt_grab(self, object_name, location, offset, radius=1.0):
        """Move vertices near a 3D location by an offset vector.

        Simulates Blender's Grab sculpt brush with smooth cosine falloff.
        Vertices at the center move the full offset; vertices at the edge of
        the radius are barely moved.

        location and offset are both in WORLD space, matching the object's
        Location in the UI.

        Use this to pull the bow of a boat model, push in dents, etc.
        """
        obj = get_object(object_name)
        if obj.type != "MESH":
            return {"success": False, "error": f"'{object_name}' is not a mesh."}

        # Same /1000 mistake as create_primitive: a sub-0.1 radius on a
        # MILLIMETERS scene is never intentional (guaranteed 0 vertices hit).
        if bpy.context.scene.unit_settings.length_unit == "MILLIMETERS" and 0 < abs(radius) < 0.1:
            raise ValueError(
                f"CRITICAL ERROR: radius={radius} is under 0.1 while the scene is configured in "
                f"MILLIMETERS. This scene's raw values ARE millimeters directly — do NOT divide by "
                f"1000 to 'convert to meters'. If you meant {radius * 1000:g}mm, pass {radius * 1000:g}, "
                f"not {radius}."
            )

        original_active = bpy.context.view_layer.objects.active
        bpy.context.view_layer.objects.active = obj
        if bpy.context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")

        world_matrix = obj.matrix_world
        world_to_local = world_matrix.inverted()
        target_world = Vector(location)
        delta_world = Vector(offset)
        delta_local = world_to_local.to_3x3() @ delta_world

        bm = bmesh.new()
        bm.from_mesh(obj.data)

        affected = 0
        nearest_dist = None
        for vert in bm.verts:
            # F14: Compute distance in WORLD space so radius semantics are invariant to object scale
            vert_world = world_matrix @ vert.co
            dist = (vert_world - target_world).length
            if nearest_dist is None or dist < nearest_dist:
                nearest_dist = dist
            if dist < radius:
                # Cosine-like smooth polynomial falloff: 1 at center, 0 at edge
                falloff = max(0.0, 1.0 - (dist / radius) ** 2)
                vert.co += delta_local * falloff
                affected += 1

        bm.to_mesh(obj.data)
        obj.data.update()
        bm.free()

        bpy.context.view_layer.objects.active = original_active

        if affected == 0:
            message = (
                f"Grab found 0 vertices within {radius} of {location} on '{object_name}'. "
                f"The nearest actual mesh vertex is {nearest_dist:.2f} units away — the location "
                f"or radius is likely wrong (check for an accidental /1000 unit conversion), not "
                f"a missing-detail issue."
            )
        else:
            message = f"Grab sculpted {affected} vertices near {location} on '{object_name}'."

        return {
            "success": True,
            "affected_vertices": affected,
            "nearest_vertex_distance": nearest_dist,
            "message": message,
        }

    def symmetrize_mesh(self, object_name, direction="POSITIVE_X"):
        """Mirror mesh geometry across an axis so both sides are perfectly symmetric.

        The source side overwrites the mirror side. Automatically enters and
        exits Sculpt Mode. The direction sets which side is the source.
        """
        obj = get_object(object_name)
        if obj.type != "MESH":
            return {"success": False, "error": f"'{object_name}' is not a mesh."}

        original_active = bpy.context.view_layer.objects.active
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

        # Map our direction string to Blender sculpt symmetry settings
        # (Blender 5.0 removed the 'direction' kwarg from sculpt.symmetrize)
        sculpt = bpy.context.scene.tool_settings.sculpt
        # Save original mirror flags and direction
        orig_x = sculpt.use_symmetry_x
        orig_y = sculpt.use_symmetry_y
        orig_z = sculpt.use_symmetry_z
        orig_dir = getattr(sculpt, "symmetrize_direction", None)

        # Enable the appropriate axis mirror based on direction
        sculpt.use_symmetry_x = direction in ("POSITIVE_X", "NEGATIVE_X")
        sculpt.use_symmetry_y = direction in ("POSITIVE_Y", "NEGATIVE_Y")
        sculpt.use_symmetry_z = direction in ("POSITIVE_Z", "NEGATIVE_Z")

        # H10: Set explicit signed symmetrize_direction on Blender 4.5 tool_settings.sculpt
        if hasattr(sculpt, "symmetrize_direction") and direction in (
            "POSITIVE_X",
            "NEGATIVE_X",
            "POSITIVE_Y",
            "NEGATIVE_Y",
            "POSITIVE_Z",
            "NEGATIVE_Z",
        ):
            sculpt.symmetrize_direction = direction

        try:
            # Blender's sculpt.symmetrize operator requires an active 3D Viewport window/region;
            # in background mode (headless), calling it causes an unhandled access violation in blender.exe.
            if getattr(bpy.app, "background", False):
                return {
                    "success": False,
                    "error": "sculpt.symmetrize requires an active 3D Viewport context (unavailable in background mode).",
                }

            bpy.ops.object.mode_set(mode="SCULPT")
            try:
                bpy.ops.sculpt.symmetrize()
            except Exception as e:
                return {"success": False, "error": f"sculpt.symmetrize() failed: {e}"}
        finally:
            # Always return to Object Mode regardless of success/failure
            try:
                bpy.ops.object.mode_set(mode="OBJECT")
            except Exception:
                pass
            # Restore original symmetry flags and direction
            sculpt.use_symmetry_x = orig_x
            sculpt.use_symmetry_y = orig_y
            sculpt.use_symmetry_z = orig_z
            if orig_dir is not None and hasattr(sculpt, "symmetrize_direction"):
                sculpt.symmetrize_direction = orig_dir
            try:
                bpy.context.view_layer.objects.active = original_active
            except Exception:
                pass

        return {
            "success": True,
            "direction": direction,
            "message": f"Symmetrized '{object_name}' using direction={direction}.",
        }

    def _sculpt_mask_attribute(self, obj):
        """Return the per-vertex sculpt_mask float attribute, or None when absent.

        Blender stores the sculpt mask in a POINT-domain float attribute named
        `sculpt_mask`. It only exists once a mask has been painted or the object
        has entered Sculpt Mode, so a missing attribute is a truthful "no mask"
        signal rather than an error.
        """
        attributes = getattr(obj.data, "attributes", None)
        if attributes is None:
            return None
        return attributes.get("sculpt_mask")

    def clear_sculpt_mask(self, object_name):
        """Clear (zero) the whole sculpt mask of a mesh.

        Deterministic attribute write — no viewport/brush context required, so
        it works in background mode. Operates without changing the active mode;
        only the active object is saved and restored.
        """
        obj = get_object(object_name)
        if obj.type != "MESH":
            return {"success": False, "error": f"'{object_name}' is not a mesh."}

        original_active = bpy.context.view_layer.objects.active
        bpy.context.view_layer.objects.active = obj
        try:
            attr = self._sculpt_mask_attribute(obj)
            if attr is None:
                return {
                    "success": True,
                    "cleared_vertices": 0,
                    "mask_present": False,
                    "message": (
                        f"No sculpt mask layer present on '{object_name}' — nothing to clear."
                    ),
                }

            cleared = 0
            for entry in attr.data:
                if entry.value != 0.0:
                    entry.value = 0.0
                    cleared += 1
            obj.data.update()
            return {
                "success": True,
                "cleared_vertices": cleared,
                "mask_present": True,
                "message": f"Cleared sculpt mask on {cleared} vertex/vertices of '{object_name}'.",
            }
        finally:
            bpy.context.view_layer.objects.active = original_active

    def invert_sculpt_mask(self, object_name):
        """Invert the whole sculpt mask of a mesh (value = 1.0 - value).

        Deterministic attribute write — no viewport/brush context required, so
        it works in background mode. Operates without changing the active mode;
        only the active object is saved and restored.
        """
        obj = get_object(object_name)
        if obj.type != "MESH":
            return {"success": False, "error": f"'{object_name}' is not a mesh."}

        original_active = bpy.context.view_layer.objects.active
        bpy.context.view_layer.objects.active = obj
        try:
            attr = self._sculpt_mask_attribute(obj)
            if attr is None:
                return {
                    "success": True,
                    "inverted_vertices": 0,
                    "mask_present": False,
                    "message": (
                        f"No sculpt mask layer present on '{object_name}' — nothing to invert."
                    ),
                }

            inverted = 0
            for entry in attr.data:
                new_value = 1.0 - entry.value
                if new_value != entry.value:
                    entry.value = new_value
                    inverted += 1
            obj.data.update()
            return {
                "success": True,
                "inverted_vertices": inverted,
                "mask_present": True,
                "message": (
                    f"Inverted sculpt mask on {inverted} vertex/vertices of '{object_name}'."
                ),
            }
        finally:
            bpy.context.view_layer.objects.active = original_active
