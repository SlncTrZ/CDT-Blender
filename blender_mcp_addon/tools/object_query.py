"""Native Blender common object-query implementation.
Wing: blender | Topic: object-query | Updated: 2026-09-14 18:31
"""

from __future__ import annotations

from collections import Counter
from typing import Any

import bpy  # type: ignore

MAX_OBJECT_LIST_LIMIT = 1000
DEFAULT_OBJECT_LIST_LIMIT = 200


def _error(kind: str, message: str, retryable: bool = False) -> dict[str, Any]:
    return {"status": "error", "kind": kind, "retryable": retryable, "message": message}


def _session_handle(obj) -> dict[str, Any] | None:
    session_uid = getattr(obj, "session_uid", None)
    if session_uid is None:
        return None
    return {
        "kind": "session_uid",
        "value": int(session_uid),
        "scope": "blender_process",
        "persistent": False,
    }


def _collection_names(obj) -> list[str]:
    return sorted(collection.name for collection in obj.users_collection)


def _summary(obj) -> dict[str, Any]:
    data = getattr(obj, "data", None)
    library = getattr(obj, "library", None)
    return {
        "name": obj.name,
        "type": obj.type,
        "collections": _collection_names(obj),
        "native_handle": _session_handle(obj),
        "extension": {
            "blender": {
                "data_name": getattr(data, "name", None),
                "parent": obj.parent.name if obj.parent else None,
                "library": library.filepath if library else None,
                "hide_viewport": bool(obj.hide_viewport),
                "hide_render": bool(obj.hide_render),
                "instance_type": obj.instance_type,
            }
        },
    }


def _detail(obj) -> dict[str, Any]:
    payload = _summary(obj)
    blender_extension = payload["extension"]["blender"]
    blender_extension.update(
        {
            "rotation_mode": obj.rotation_mode,
            "matrix_world": [list(row) for row in obj.matrix_world],
            "modifiers": [
                {"name": modifier.name, "type": modifier.type} for modifier in obj.modifiers
            ],
        }
    )
    if obj.type == "MESH" and obj.data is not None:
        blender_extension["geometry"] = {
            "vertices": len(obj.data.vertices),
            "edges": len(obj.data.edges),
            "faces": len(obj.data.polygons),
        }
    payload.update(
        {
            "location": list(obj.location),
            "rotation": list(obj.rotation_euler),
            "scale": list(obj.scale),
            "dimensions": list(obj.dimensions),
        }
    )
    return payload


class ObjectQueryTools:
    """Read-only common object-query operations scoped to the active scene."""

    def _matching_objects(self, type: str | None = None, collection: str | None = None):
        requested_type = type.upper() if type else None
        objects = list(bpy.context.scene.objects)
        if requested_type:
            objects = [obj for obj in objects if obj.type == requested_type]
        if collection:
            objects = [obj for obj in objects if collection in _collection_names(obj)]
        return sorted(objects, key=lambda obj: (obj.name.casefold(), obj.name))

    def object_list(
        self,
        type: str | None = None,
        collection: str | None = None,
        offset: int = 0,
        limit: int = DEFAULT_OBJECT_LIST_LIMIT,
    ):
        if offset < 0:
            return _error("validation_error", "offset must be >= 0.")
        if limit < 1 or limit > MAX_OBJECT_LIST_LIMIT:
            return _error(
                "validation_error",
                f"limit must be between 1 and {MAX_OBJECT_LIST_LIMIT}.",
            )

        objects = self._matching_objects(type=type, collection=collection)
        window = objects[offset : offset + limit]
        return {
            "status": "success",
            "scene": bpy.context.scene.name,
            "total": len(objects),
            "offset": offset,
            "limit": limit,
            "returned": len(window),
            "truncated": offset + len(window) < len(objects),
            "objects": [_summary(obj) for obj in window],
        }

    def object_get(self, name: str):
        obj = bpy.context.scene.objects.get(name)
        if obj is None:
            return _error("not_found", f"Object is not linked to the active scene: {name}")
        payload = _detail(obj)
        payload.update({"status": "success", "scene": bpy.context.scene.name})
        return payload

    def object_count(self, type: str | None = None, collection: str | None = None):
        objects = self._matching_objects(type=type, collection=collection)
        counts = Counter(obj.type for obj in objects)
        return {
            "status": "success",
            "scene": bpy.context.scene.name,
            "count": len(objects),
            "by_type": dict(sorted(counts.items())),
        }
