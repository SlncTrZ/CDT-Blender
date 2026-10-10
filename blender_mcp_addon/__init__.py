# blender_mcp_addon/__init__.py

import bpy  # type: ignore

from .server import BlenderMCPServer
from .utils import DEFAULT_PORT

bl_info = {
    "name": "Blender MCP Bridge",
    "author": "seehiong",
    "version": (0, 2, 0),
    "blender": (4, 5, 3),
    "location": "View3D > Sidebar > MCP",
    "description": "Blender Model Context Protocol (MCP) server for AI agents",
    "category": "Development",
}

_server_instance = None


class BLENDERMCP_Preferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    auto_start: bpy.props.BoolProperty(
        name="Start bridge when Blender opens",
        default=False,
        description="Attach to the current document; does not create or reopen documents",
    )
    port: bpy.props.IntProperty(name="Loopback port", default=DEFAULT_PORT, min=1024, max=65535)

    def draw(self, context):
        self.layout.prop(self, "auto_start")
        self.layout.prop(self, "port")


def _preferences():
    addon = bpy.context.preferences.addons.get(__package__)
    return addon.preferences if addon else None


def _start_configured_server():
    global _server_instance
    prefs = _preferences()
    if _server_instance is None:
        _server_instance = BlenderMCPServer()
    port = prefs.port if prefs else DEFAULT_PORT
    return _server_instance.start_server(host="127.0.0.1", port=port)


def _auto_start():
    prefs = _preferences()
    if prefs and prefs.auto_start:
        _start_configured_server()
    return None


class BLENDERMCP_OT_StartServer(bpy.types.Operator):
    """Start MCP Server"""

    bl_idname = "blendermcp.start_server"
    bl_label = "Start MCP Server"

    def execute(self, context):
        global _server_instance
        result = _start_configured_server()
        if result["ok"]:
            message = (
                "MCP Server already running" if result["already_running"] else "MCP Server started"
            )
            self.report({"INFO"}, message)
            return {"FINISHED"}
        self.report({"ERROR"}, result["error"])
        return {"CANCELLED"}


class BLENDERMCP_OT_StopServer(bpy.types.Operator):
    """Stop MCP Server"""

    bl_idname = "blendermcp.stop_server"
    bl_label = "Stop MCP Server"

    def execute(self, context):
        global _server_instance
        if _server_instance:
            _server_instance.stop_server()
            self.report({"INFO"}, "MCP Server stopped")
        return {"FINISHED"}


class BLENDERMCP_PT_Panel(bpy.types.Panel):
    """MCP Control Panel"""

    bl_label = "Blender MCP Bridge"
    bl_idname = "BLENDERMCP_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Blender MCP"

    def draw(self, context):
        global _server_instance
        layout = self.layout
        layout.label(text="Blender MCP Bridge")

        if _server_instance and _server_instance.running:
            row = layout.row()
            row.label(text="Status: Running", icon="CHECKMARK")
        else:
            row = layout.row()
            row.label(text="Status: Stopped", icon="X")
            row.alert = True
            if _server_instance and _server_instance.last_error:
                layout.label(text=_server_instance.last_error, icon="ERROR")

        layout.operator("blendermcp.start_server")
        layout.operator("blendermcp.stop_server")
        layout.separator()
        layout.label(text=f"Port: {DEFAULT_PORT}")
        layout.label(text="45+ Structured Tools")


def register():
    bpy.utils.register_class(BLENDERMCP_Preferences)
    bpy.utils.register_class(BLENDERMCP_OT_StartServer)
    bpy.utils.register_class(BLENDERMCP_OT_StopServer)
    bpy.utils.register_class(BLENDERMCP_PT_Panel)
    bpy.app.timers.register(_auto_start, first_interval=1.0, persistent=True)


def unregister():
    global _server_instance
    if bpy.app.timers.is_registered(_auto_start):
        bpy.app.timers.unregister(_auto_start)
    if _server_instance:
        _server_instance.stop_server()
        _server_instance = None
    bpy.utils.unregister_class(BLENDERMCP_PT_Panel)
    bpy.utils.unregister_class(BLENDERMCP_OT_StopServer)
    bpy.utils.unregister_class(BLENDERMCP_OT_StartServer)
    bpy.utils.unregister_class(BLENDERMCP_Preferences)


if __name__ == "__main__":
    register()
