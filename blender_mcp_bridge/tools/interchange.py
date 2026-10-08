# blender_mcp_bridge/tools/interchange.py
#
# Fork of seehiong/blender-mcp-bridge (MIT, see ATTRIBUTION.md).
# SlncTrZ provider-shell adaptation by SlncTrZ / Truong Cong Dinh.
#
# DCC interchange for the Unreal Engine 5 lane: FBX and glTF export with
# explicit axis/scale conventions. File paths are contained by
# BLENDER_ALLOW_ROOTS on the server before reaching Blender.

from mcp import types


def get_interchange_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="export_fbx",
            description=(
                "Export the scene (or selection) to FBX for DCC interchange "
                "(Unreal Engine 5 lane). Units are meters; axis convention is "
                "explicit — UE5 imports Y-forward/Z-up via its own preset, so "
                "export Blender-native -Z-forward/Y-up and convert on import."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "filepath": {
                        "type": "string",
                        "description": "Destination .fbx path (must sit under BLENDER_ALLOW_ROOTS)",
                    },
                    "export_selected": {
                        "type": "boolean",
                        "default": False,
                        "description": "Export only selected objects",
                    },
                    "apply_scale": {
                        "type": "string",
                        "enum": [
                            "FBX_SCALE_NONE",
                            "FBX_SCALE_UNITS",
                            "FBX_SCALE_CUSTOM",
                            "FBX_SCALE_ALL",
                        ],
                        "default": "FBX_SCALE_UNITS",
                    },
                    "bake_space_transform": {
                        "type": "boolean",
                        "default": False,
                        "description": "Bake global transform into vertices (leave off unless a downstream tool needs it)",
                    },
                },
                "required": ["filepath"],
            },
        ),
        types.Tool(
            name="export_gltf",
            description=(
                "Export the scene (or selection) to glTF 2.0 (.glb/.gltf) for "
                "DCC interchange. glTF is Y-up; Blender converts on export."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "filepath": {
                        "type": "string",
                        "description": "Destination path ending .glb or .gltf (must sit under BLENDER_ALLOW_ROOTS)",
                    },
                    "export_selected": {
                        "type": "boolean",
                        "default": False,
                        "description": "Export only selected objects",
                    },
                    "export_materials": {
                        "type": "string",
                        "enum": ["EXPORT", "PLACEHOLDER", "NONE"],
                        "default": "EXPORT",
                    },
                },
                "required": ["filepath"],
            },
        ),
    ]
