# blender_mcp_addon/server.py

import json
import platform
import queue
import socket
import threading
import traceback

import bpy  # type: ignore

from .tools.animation import AnimationTools
from .tools.camera import CameraTools
from .tools.collections import CollectionTools
from .tools.document import DocumentTools
from .tools.history import HistoryTools
from .tools.interchange import InterchangeTools
from .tools.lighting import LightTools
from .tools.materials import MaterialTools
from .tools.modeling import ModelingTools
from .tools.object_query import ObjectQueryTools
from .tools.printing import PrintingTools
from .tools.rendering import RenderingTools
from .tools.scene import SceneTools
from .tools.sculpting import SculptingTools
from .utils import DEFAULT_HOST, DEFAULT_PORT


class BlenderMCPServer(
    DocumentTools,
    ObjectQueryTools,
    SceneTools,
    CollectionTools,
    ModelingTools,
    MaterialTools,
    AnimationTools,
    RenderingTools,
    CameraTools,
    LightTools,
    HistoryTools,
    InterchangeTools,
    PrintingTools,
    SculptingTools,
):
    """Blender MCP addon server with componentized tools"""

    def __init__(self):
        self.server_socket: socket.socket | None = None
        self.running = False
        self.server_thread = None
        self.command_queue = queue.Queue()
        self.last_error = None
        self.timer_handle = None

    def start_server(self, host=DEFAULT_HOST, port=DEFAULT_PORT):
        if self.running:
            self._register_timer()
            return {"ok": True, "state": "running", "already_running": True}

        try:
            self.addon_log("Attempting to start MCP Server...")
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((host, port))
            self.server_socket.listen(128)  # Increased backlog for rapid n8n requests
            self.running = True
            self.server_thread = threading.Thread(target=self._server_loop, daemon=True)
            self.server_thread.start()
            self._register_timer()
            self.last_error = None
            self.addon_log(f"MCP Server successfully started on {host}:{port}")
            print(f"MCP Server started on {host}:{port}")
            return {"ok": True, "state": "running", "already_running": False}
        except Exception as e:
            error_msg = f"Failed to start server: {e}"
            self.last_error = error_msg
            print(error_msg)
            self.addon_log(error_msg)
            self.stop_server()
            return {"ok": False, "state": "stopped", "error": error_msg}

    def _register_timer(self):
        if self.timer_handle is None:
            self.timer_handle = self._process_queue
        if not bpy.app.timers.is_registered(self.timer_handle):
            bpy.app.timers.register(self.timer_handle, persistent=True)

    def _unregister_timer(self):
        if self.timer_handle is None:
            return
        if bpy.app.timers.is_registered(self.timer_handle):
            bpy.app.timers.unregister(self.timer_handle)
        self.timer_handle = None

    def stop_server(self):
        self.running = False

        server_socket = self.server_socket
        self.server_socket = None
        if server_socket is not None:
            try:
                server_socket.close()
            except Exception:
                pass

        self._unregister_timer()

        server_thread = self.server_thread
        self.server_thread = None
        if server_thread is not None and server_thread is not threading.current_thread():
            try:
                server_thread.join(timeout=2.0)
            except Exception:
                pass

        print("MCP Server stopped")
        return {"ok": True, "state": "stopped"}

    def _server_loop(self):
        while self.running:
            try:
                if not self.server_socket:  # type: ignore
                    break
                self.server_socket.settimeout(1.0)
                try:
                    client, _ = self.server_socket.accept()
                    threading.Thread(
                        target=self._handle_client, args=(client,), daemon=True
                    ).start()
                except TimeoutError:
                    continue
            except Exception as e:
                if self.running:
                    print(f"[MCP] Server loop error: {e}")

    def _handle_client(self, client):
        try:
            client.settimeout(180.0)
            data = client.recv(8192)
            if not data:
                return
            command = json.loads(data.decode("utf-8"))
            response = self.handle_command(command)
            client.sendall(json.dumps(response).encode("utf-8"))
        except Exception as e:
            print(f"[MCP] Client error: {e}")
            try:
                client.sendall(json.dumps({"status": "error", "message": str(e)}).encode("utf-8"))
            except Exception:
                pass
        finally:
            try:
                client.close()
            except Exception:
                pass

    def handle_command(self, command):
        if not self.running:
            return {"status": "error", "message": "Server not running"}
        result_event, res_container = threading.Event(), {"result": None}
        self.command_queue.put(
            {"command": command, "event": result_event, "container": res_container}
        )
        if not result_event.wait(timeout=60.0):
            return {"status": "error", "message": "Command timed out"}
        return res_container["result"]

    def get_runtime_context(self):
        """Return current Blender process/context facts without mutating state."""
        active_object = bpy.context.active_object
        active_mode = bpy.context.mode
        window_manager = bpy.context.window_manager
        windows = list(window_manager.windows) if window_manager else []
        background = bool(bpy.app.background)
        ui_available = not background and bool(windows)

        view3d_available = False
        if ui_available:
            view3d_available = any(
                area.type == "VIEW_3D" and any(region.type == "WINDOW" for region in area.regions)
                for window in windows
                for area in window.screen.areas
            )

        active_object_payload = None
        if active_object is not None:
            active_object_payload = {
                "name": active_object.name,
                "type": active_object.type,
            }

        is_active_mesh = active_object is not None and active_object.type == "MESH"
        scene = bpy.context.scene

        return {
            "blender_version": bpy.app.version_string,
            "blender_version_tuple": list(bpy.app.version),
            "platform_system": platform.system(),
            "background": background,
            "ui_available": ui_available,
            "view3d_available": view3d_available,
            "active_mode": active_mode,
            "active_object": active_object_payload,
            "mesh_editable": bool(is_active_mesh and active_mode == "EDIT_MESH"),
            "sculpt_context_available": bool(
                ui_available and view3d_available and is_active_mesh and active_mode == "SCULPT"
            ),
            "render_engine": scene.render.engine if scene else None,
        }

    def addon_log(self, msg):
        try:
            import os

            log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "blender_addon.log")
            with open(log_path, "a") as f:
                f.write(msg + "\n")
        except Exception:
            pass

    def _process_queue(self):
        if not self.running:
            return None
        try:
            # self.addon_log("Timer tick check queue...")
            while not self.command_queue.empty():
                try:
                    item = self.command_queue.get_nowait()
                    if not item:
                        continue
                    cmd, event, res = item["command"], item["event"], item["container"]
                    cmd_type = cmd.get("type", "")
                    self.addon_log(f"Processing command: {cmd_type}")
                    try:
                        res["result"] = self.execute_command(cmd)
                        self.addon_log(f"Command {cmd_type} executed successfully")

                        # Push to Undo Stack if it's a state-changing command
                        if (
                            cmd_type
                            and not cmd_type.startswith("get_")
                            and cmd_type
                            not in [
                                "undo",
                                "redo",
                                "render_frame",
                                "render_animation",
                                # Creates and deletes its own temp camera/lights
                                # and leaves the scene as it found it — pushing an
                                # undo step would just clutter the user's history.
                                "generate_views",
                                "extract_sketch",
                            ]
                        ):
                            try:
                                bpy.ops.ed.undo_push(message=f"MCP: {cmd_type}")
                            except Exception as e:
                                self.addon_log(f"Failed to push undo: {e}")

                    except Exception as e:
                        traceback.print_exc()
                        self.addon_log(f"Execution error on {cmd_type}: {e}")
                        res["result"] = {
                            "status": "error",
                            "message": f"Execution error: {e}",
                        }
                    finally:
                        event.set()
                        self.addon_log(f"Signaled event for {cmd_type}")
                except Exception as e:
                    self.addon_log(f"Queue item processing error: {e}")
                    traceback.print_exc()
        except Exception as e:
            self.addon_log(f"Critical Timer Error: {e}")
            traceback.print_exc()

        return 0.005

    def execute_command(self, command):
        cmd_type, params, rid = (
            command.get("type"),
            command.get("params", {}),
            command.get("request_id", "unknown"),
        )
        print(f"[MCP][{rid}] Executing: {cmd_type}")
        print(f"[MCP][{rid}] Params: {params}")

        # Map types to methods (inherited from tool classes)
        # This keeps the dispatcher dynamic and maintains compatibility with existing client
        methods = {
            # Runtime discovery (internal bridge command; not advertised as an MCP tool)
            "get_runtime_context": self.get_runtime_context,
            # Common document lifecycle
            "document_new": self.document_new,
            "document_open": self.document_open,
            "document_info": self.document_info,
            "document_save": self.document_save,
            "document_save_as": self.document_save_as,
            "document_close": self.document_close,
            # Common object query
            "object_list": self.object_list,
            "object_get": self.object_get,
            "object_count": self.object_count,
            # Common organization query
            "organization_list": self.organization_list,
            # Common object transforms
            "object_move": self.object_move,
            "object_rotate": self.object_rotate,
            "object_scale": self.object_scale,
            # Scene
            "get_scene_info": self.get_scene_info,
            "get_object_info": self.get_object_info,
            "get_viewport_screenshot": self.get_viewport_screenshot,
            "get_distance": self.get_distance,
            # Collections
            "create_collection": self.create_collection,
            "set_active_collection": self.set_active_collection,
            "move_to_collection": self.move_to_collection,
            "get_collections": self.get_collections,
            "remove_collection": self.remove_collection,
            "duplicate_collection": self.duplicate_collection,
            "set_collection_visibility": self.set_collection_visibility,
            # Modeling
            "create_primitive": self.create_primitive,
            "create_cube": self.create_cube,
            "create_cylinder": self.create_cylinder,
            "create_sphere": self.create_sphere,
            "create_cone": self.create_cone,
            "create_icosphere": self.create_icosphere,
            "create_torus": self.create_torus,
            "create_text": self.create_text,
            "create_plane": self.create_plane,
            "create_empty": self.create_empty,
            "create_polygon": self.create_polygon,
            "create_watertight_plate": self.create_watertight_plate,
            "create_curve": self.create_curve,
            "extract_sketch": self.extract_sketch,
            "duplicate_object": self.duplicate_object,
            "duplicate_selection": self.duplicate_selection,
            "create_and_array": self.create_and_array,
            "batch_transform": self.batch_transform,
            "apply_modifier": self.apply_modifier,
            "copy_modifier": self.copy_modifier,
            "remove_modifier": self.remove_modifier,
            "boolean_operation": self.boolean_operation,
            "apply_all_modifiers": self.apply_all_modifiers,
            "transform_object": self.transform_object,
            "circular_array": self.circular_array,
            "select_objects": self.select_objects,
            "select_by_pattern": self.select_by_pattern,
            "select_by_collection": self.select_by_collection,
            "delete_object": self.delete_object,
            "set_object_dimensions": self.set_object_dimensions,
            "join_objects": self.join_objects,
            "random_distribute": self.random_distribute,
            "apply_transforms": self.apply_transforms,
            "extrude_mesh": self.extrude_mesh,
            "inset_faces": self.inset_faces,
            "shear_mesh": self.shear_mesh,
            "invert_mesh_selection": self.invert_mesh_selection,
            "set_object_visibility": self.set_object_visibility,
            "convert_to_mesh": self.convert_to_mesh,
            "separate_loose_parts": self.separate_loose_parts,
            # Architectural (ArchBuilder)
            "build_room_shell": self.build_room_shell,
            "build_wall_segment": self.build_wall_segment,
            "build_wall_with_door": self.build_wall_with_door,
            "build_column": self.build_column,
            "set_view": self.set_view,
            # MEP Systems
            "build_pipe_run": self.build_pipe_run,
            "build_cable_tray": self.build_cable_tray,
            "add_tray_support": self.add_tray_support,
            # Animation
            "set_keyframe": self.set_keyframe,
            "get_keyframes": self.get_keyframes,
            "set_timeline_range": self.set_timeline_range,
            "play_animation": self.play_animation,
            # Rendering
            "configure_render_settings": self.configure_render_settings,
            "render_frame": self.render_frame,
            "render_animation": self.render_animation,
            "generate_views": self.generate_views,
            # Material
            "create_material": self.create_material,
            "set_material_properties": self.set_material_properties,
            "assign_material": self.assign_material,
            "add_shader_node": self.add_shader_node,
            "connect_shader_nodes": self.connect_shader_nodes,
            "assign_builtin_texture": self.assign_builtin_texture,
            "assign_texture_map": self.assign_texture_map,
            # Camera
            "create_camera": self.create_camera,
            "set_active_camera": self.set_active_camera,
            "camera_look_at": self.camera_look_at,
            # Light
            "create_light": self.create_light,
            "configure_light": self.configure_light,
            "set_world_background": self.set_world_background,
            # Printing
            "set_scene_units": self.set_scene_units,
            "check_mesh_for_printing": self.check_mesh_for_printing,
            "repair_mesh": self.repair_mesh,
            "apply_voxel_remesh": self.apply_voxel_remesh,
            "export_model": self.export_model,
            "import_model": self.import_model,
            # Sculpting
            "enter_sculpt_mode": self.enter_sculpt_mode,
            "exit_sculpt_mode": self.exit_sculpt_mode,
            "set_dyntopo": self.set_dyntopo,
            "apply_sculpt_smooth": self.apply_sculpt_smooth,
            "sculpt_inflate": self.sculpt_inflate,
            "sculpt_grab": self.sculpt_grab,
            "symmetrize_mesh": self.symmetrize_mesh,
            # History
            "undo": self.undo_action,
            "redo": self.redo_action,
            # Interchange (CDT fork: Unreal Engine 5 lane)
            "export_fbx": self.export_fbx,
            "export_gltf": self.export_gltf,
        }

        handler = methods.get(cmd_type)
        if not handler:
            return {"status": "error", "message": f"Unknown command: {cmd_type}"}

        try:
            result = handler(**params)
            if isinstance(result, dict) and "message" in result:
                msg = result["message"]
                if not msg.startswith(f"[{rid}]"):
                    result["message"] = (
                        f"✓ [{rid}] {msg[2:]}" if msg.startswith("✓ ") else f"[{rid}] {msg}"
                    )
            return {"status": "success", "result": result}
        except Exception as e:
            print(f"[MCP] Handler error: {e}")
            traceback.print_exc()
            return {"status": "error", "message": str(e)}
