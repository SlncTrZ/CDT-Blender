"""Native Blender document lifecycle implementation.
Wing: blender | Topic: document-lifecycle | Updated: 2026-09-14 17:05
"""

from __future__ import annotations

import os
from typing import Any

import bpy  # type: ignore


def _error(kind: str, message: str, retryable: bool = False) -> dict[str, Any]:
    return {"status": "error", "kind": kind, "retryable": retryable, "message": message}


def _canonical(path: str) -> str:
    return os.path.normcase(os.path.realpath(os.path.abspath(path)))


def _path_is_allowed(path: str, allow_roots: list[str] | None) -> bool:
    if not allow_roots:
        return False
    needle = _canonical(path)
    for root in allow_roots:
        canonical_root = _canonical(root)
        try:
            if os.path.commonpath([needle, canonical_root]) == canonical_root:
                return True
        except ValueError:
            continue
    return False


class DocumentTools:
    """Common lifecycle operations mapped onto Blender's single-document process."""

    def _document_info(self) -> dict[str, Any]:
        scene = bpy.context.scene
        filepath = bpy.data.filepath
        return {
            "status": "success",
            "filepath": filepath.replace("\\", "/") if filepath else "",
            "name": os.path.basename(filepath) if filepath else "Untitled",
            "is_saved": bool(bpy.data.is_saved),
            "is_dirty": bool(bpy.data.is_dirty),
            "dirty_signal_reliable": not bool(bpy.app.background),
            "loaded_file_version": list(bpy.data.version),
            "blender_version": bpy.app.version_string,
            "scene": scene.name if scene else None,
            "scene_count": len(bpy.data.scenes),
            "object_count": len(scene.objects) if scene else 0,
            "unit_system": scene.unit_settings.system if scene else None,
            "length_unit": scene.unit_settings.length_unit if scene else None,
        }

    def _guard_unsaved(self, discard_unsaved: bool) -> dict[str, Any] | None:
        if discard_unsaved:
            return None
        if bpy.app.background:
            return _error(
                "conflict",
                "Background Blender cannot reliably prove that the current document is clean; retry with discard_unsaved=true to authorize replacement explicitly.",
            )
        if bpy.data.is_dirty:
            return _error(
                "conflict",
                "Current Blender document has unsaved changes. Save it or retry with discard_unsaved=true.",
            )
        return None

    def document_new(self, discard_unsaved: bool = False):
        if problem := self._guard_unsaved(discard_unsaved):
            return problem
        result = bpy.ops.wm.read_homefile(
            use_factory_startup=True,
            use_empty=True,
            load_ui=False,
        )
        if "FINISHED" not in result:
            return _error("internal_error", f"Blender failed to create a new document: {result}")
        payload = self._document_info()
        payload["message"] = "Created a new empty Blender document."
        return payload

    def document_open(
        self,
        filepath: str,
        discard_unsaved: bool = False,
        load_ui: bool = False,
        _allow_roots: list[str] | None = None,
    ):
        if problem := self._guard_unsaved(discard_unsaved):
            return problem
        if not filepath.lower().endswith(".blend"):
            return _error("validation_error", "document_open accepts only .blend files.")
        if not _path_is_allowed(filepath, _allow_roots):
            return _error(
                "validation_error", "Document path is outside the configured allow-roots."
            )
        if not os.path.isfile(filepath):
            return _error("not_found", f"Blender document does not exist: {filepath}")

        result = bpy.ops.wm.open_mainfile(
            filepath=filepath,
            load_ui=load_ui,
            use_scripts=False,
            display_file_selector=False,
        )
        if "FINISHED" not in result:
            return _error("internal_error", f"Blender failed to open document: {result}")
        payload = self._document_info()
        payload["message"] = f"Opened Blender document: {payload['filepath']}"
        return payload

    def document_info(self):
        payload = self._document_info()
        payload["message"] = "Retrieved current Blender document information."
        return payload

    def document_save(self, _allow_roots: list[str] | None = None):
        filepath = bpy.data.filepath
        if not filepath:
            return _error(
                "conflict",
                "Current Blender document has no filepath. Use document_save_as first.",
            )
        if not _path_is_allowed(filepath, _allow_roots):
            return _error(
                "validation_error",
                "Current Blender document path is outside the configured allow-roots.",
            )
        if not filepath.lower().endswith(".blend"):
            return _error("validation_error", "Current document path is not a .blend file.")

        result = bpy.ops.wm.save_mainfile(filepath=filepath, check_existing=False)
        if "FINISHED" not in result:
            return _error("internal_error", f"Blender failed to save document: {result}")
        payload = self._document_info()
        payload["message"] = f"Saved Blender document: {payload['filepath']}"
        return payload

    def document_save_as(
        self,
        filepath: str,
        overwrite: bool = False,
        compress: bool = False,
        _allow_roots: list[str] | None = None,
    ):
        if not filepath.lower().endswith(".blend"):
            return _error("validation_error", "document_save_as requires a .blend destination.")
        if not _path_is_allowed(filepath, _allow_roots):
            return _error(
                "validation_error", "Document path is outside the configured allow-roots."
            )
        parent = os.path.dirname(os.path.abspath(filepath)) or os.getcwd()
        if not os.path.isdir(parent):
            return _error("not_found", f"Destination directory does not exist: {parent}")
        if os.path.exists(filepath) and not overwrite:
            return _error(
                "conflict",
                "Destination already exists. Retry with overwrite=true to replace it.",
            )

        result = bpy.ops.wm.save_as_mainfile(
            filepath=filepath,
            check_existing=False,
            compress=compress,
            relative_remap=True,
            copy=False,
        )
        if "FINISHED" not in result:
            return _error("internal_error", f"Blender failed to save document as: {result}")
        payload = self._document_info()
        payload["message"] = f"Saved Blender document as: {payload['filepath']}"
        return payload

    def document_close(self, discard_unsaved: bool = False):
        if problem := self._guard_unsaved(discard_unsaved):
            return problem
        closed_filepath = bpy.data.filepath.replace("\\", "/") if bpy.data.filepath else ""
        result = bpy.ops.wm.read_homefile(
            use_factory_startup=True,
            use_empty=True,
            load_ui=False,
        )
        if "FINISHED" not in result:
            return _error("internal_error", f"Blender failed to close document: {result}")
        payload = self._document_info()
        payload["closed_filepath"] = closed_filepath
        payload["message"] = (
            "Closed the logical document and reset Blender to an empty unsaved file."
        )
        return payload
