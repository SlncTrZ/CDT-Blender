"""Document lifecycle tool schemas.
Wing: blender | Topic: document-lifecycle | Updated: 2026-09-14 17:05
"""

from mcp import types


def get_document_tools() -> list[types.Tool]:
    """Return the common document lifecycle surface for Blender."""
    discard = {
        "discard_unsaved": {
            "type": "boolean",
            "default": False,
            "description": "Allow replacing the current document even when Blender reports unsaved changes.",
        }
    }
    return [
        types.Tool(
            name="document_new",
            description="Replace the current file with a new empty Blender document.",
            inputSchema={"type": "object", "properties": discard},
        ),
        types.Tool(
            name="document_open",
            description="Open an existing .blend file inside the configured allow-roots.",
            inputSchema={
                "type": "object",
                "properties": {
                    "filepath": {
                        "type": "string",
                        "description": "Path to an existing .blend file.",
                    },
                    "discard_unsaved": discard["discard_unsaved"],
                    "load_ui": {
                        "type": "boolean",
                        "default": False,
                        "description": "Load UI layout stored in the file. Keep false for deterministic executor use.",
                    },
                },
                "required": ["filepath"],
            },
        ),
        types.Tool(
            name="document_info",
            description="Read current Blender document identity, save state, scene and unit metadata.",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="document_save",
            description="Save the current .blend file to its existing path; unsaved documents must use document_save_as.",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="document_save_as",
            description="Save the current Blender document to a .blend path inside the configured allow-roots.",
            inputSchema={
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "Destination .blend path."},
                    "overwrite": {
                        "type": "boolean",
                        "default": False,
                        "description": "Permit replacing an existing .blend file.",
                    },
                    "compress": {
                        "type": "boolean",
                        "default": False,
                        "description": "Enable Blender file compression.",
                    },
                },
                "required": ["filepath"],
            },
        ),
        types.Tool(
            name="document_close",
            description="Close the current logical document without terminating Blender by resetting to an empty unsaved file.",
            inputSchema={"type": "object", "properties": discard},
        ),
    ]
