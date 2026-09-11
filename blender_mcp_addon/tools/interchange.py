# blender_mcp_addon/tools/interchange.py
#
# Fork of seehiong/blender-mcp-bridge (MIT, see ATTRIBUTION.md).
# SlncTrZ provider-shell adaptation by SlncTrZ / Truong Cong Dinh.
#
# DCC interchange handlers (Unreal Engine 5 lane). Paths arrive already
# contained by BLENDER_ALLOW_ROOTS on the bridge; the basename/extension is
# still validated here so a malformed call fails loudly, never silently.

import os

import bpy  # type: ignore


class InterchangeTools:
    """FBX / glTF export handlers."""

    def _checked_path(self, filepath, wanted_exts):
        if not isinstance(filepath, str) or not filepath.strip():
            return None, "filepath must be a non-empty string."
        ext = os.path.splitext(filepath)[1].lower()
        if ext not in wanted_exts:
            return None, f"filepath must end with one of {sorted(wanted_exts)} (got '{ext}')."
        directory = os.path.dirname(os.path.abspath(filepath))
        try:
            os.makedirs(directory, exist_ok=True)
        except Exception as e:
            return None, f"cannot create destination directory '{directory}': {e}"
        return filepath, None

    def export_fbx(
        self,
        filepath,
        export_selected=False,
        apply_scale="FBX_SCALE_UNITS",
        bake_space_transform=False,
    ):
        """Export scene/selection to FBX (Blender-native axes; convert on UE5 import)."""
        path, error = self._checked_path(filepath, {".fbx"})
        if error:
            return {"status": "error", "message": error}
        try:
            bpy.ops.export_scene.fbx(
                filepath=path,
                use_selection=bool(export_selected),
                global_scale=1.0,
                apply_unit_scale=True,
                apply_scale_options=apply_scale,
                bake_space_transform=bool(bake_space_transform),
                axis_forward="-Z",
                axis_up="Y",
            )
        except Exception as e:
            return {"status": "error", "message": f"FBX export failed: {e}"}
        return {
            "status": "success",
            "filepath": path,
            "message": f"Exported FBX to '{path}'.",
        }

    def export_gltf(self, filepath, export_selected=False, export_materials="EXPORT"):
        """Export scene/selection to glTF 2.0 (.glb/.gltf)."""
        path, error = self._checked_path(filepath, {".glb", ".gltf"})
        if error:
            return {"status": "error", "message": error}
        try:
            bpy.ops.export_scene.gltf(
                filepath=path,
                use_selection=bool(export_selected),
                export_format="GLB" if path.lower().endswith(".glb") else "GLTF_SEPARATE",
                export_materials=export_materials,
            )
        except Exception as e:
            return {"status": "error", "message": f"glTF export failed: {e}"}
        return {
            "status": "success",
            "filepath": path,
            "message": f"Exported glTF to '{path}'.",
        }
