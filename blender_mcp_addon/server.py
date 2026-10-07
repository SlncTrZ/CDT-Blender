# blender_mcp_addon/server.py

import json
import os
import platform
import queue
import socket
import threading
import time
import traceback
import uuid
from collections.abc import Callable
from typing import Any

import bpy  # type: ignore

from .lifecycle import MutationLifecycleManager
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

MAX_REQUEST_BYTES = 1024 * 1024
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
REQUEST_RECEIVE_TIMEOUT_SECONDS = 5.0
SOCKET_CHUNK_BYTES = 4096

ADMISSION_QUEUE_MAXSIZE = 16
MAX_COMMANDS_PER_TICK = 4
MAX_ACTIVE_CLIENT_THREADS = 16

COMMAND_WAIT_TIMEOUT_SECONDS = 60.0

# B2 LAN-bind refusal: the addon socket is workstation-local by design. Only
# the workstation runtime agent talks to it, and only over loopback. A wider
# bind is refused unless the operator explicitly opts in (migration control
# §19: no direct LAN addon exposure; remote access goes through the
# authenticated RuntimeTransport + agent boundary instead).
_ADDON_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
_ADDON_ALLOW_REMOTE_ENV = "BLENDER_ADDON_ALLOW_REMOTE"


def _addon_bind_allowed(host: object) -> bool:
    if str(host or "").lower() in _ADDON_LOOPBACK_HOSTS:
        return True
    return os.environ.get(_ADDON_ALLOW_REMOTE_ENV) == "1"


def _transport_error(kind, message, *, retryable=False):
    return {
        "status": "error",
        "kind": kind,
        "retryable": retryable,
        "message": message,
    }


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
        self.command_queue: queue.Queue = queue.Queue(maxsize=ADMISSION_QUEUE_MAXSIZE)
        self.last_error = None
        self.timer_handle = None
        self.lifecycle = MutationLifecycleManager()
        self._client_slots = threading.BoundedSemaphore(MAX_ACTIVE_CLIENT_THREADS)

    def start_server(self, host=DEFAULT_HOST, port=DEFAULT_PORT):
        if self.running:
            self._register_timer()
            return {"ok": True, "state": "running", "already_running": True}

        if not _addon_bind_allowed(host):
            error_msg = (
                f"Refusing non-loopback addon bind {host!r}: the addon socket "
                "is workstation-local. Remote access must go through the "
                "authenticated workstation runtime agent instead. To override, "
                f"set {_ADDON_ALLOW_REMOTE_ENV}=1."
            )
            self.last_error = error_msg
            self.addon_log(error_msg)
            return {"ok": False, "state": "refused", "error": error_msg}

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
        # F07: Do NOT discard lifecycle receipts / uncertainty state on timer unregister!

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
                except TimeoutError:
                    continue
                # H12: bound concurrent client handler threads so unbounded
                # socket connections cannot exhaust threads. Reject with a
                # typed overload when the cap is reached.
                if not self._client_slots.acquire(blocking=False):
                    try:
                        client.sendall(
                            self._encode_response(
                                _transport_error(
                                    "rate_limited",
                                    "Concurrent client connection limit reached; "
                                    "rejecting new client.",
                                    retryable=True,
                                )
                            )
                        )
                    except Exception:
                        pass
                    try:
                        client.close()
                    except Exception:
                        pass
                    continue
                threading.Thread(
                    target=self._handle_client_slot, args=(client,), daemon=True
                ).start()
            except Exception as e:
                if self.running:
                    print(f"[MCP] Server loop error: {e}")

    def _handle_client_slot(self, client):
        """Run a client handler while holding a concurrency slot.

        The slot is acquired by _server_loop before the handler thread is
        spawned and is always released here (H12: bounded client threads).
        """
        try:
            self._handle_client(client)
        finally:
            self._client_slots.release()

    def _receive_request(self, client):
        deadline = time.monotonic() + REQUEST_RECEIVE_TIMEOUT_SECONDS
        data = bytearray()

        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None, _transport_error(
                    "timeout",
                    "Request receive deadline exceeded.",
                    retryable=True,
                )

            try:
                client.settimeout(remaining)
                chunk = client.recv(SOCKET_CHUNK_BYTES)
            except TimeoutError:
                return None, _transport_error(
                    "timeout",
                    "Request receive deadline exceeded.",
                    retryable=True,
                )

            if not chunk:
                return None, _transport_error(
                    "validation_error",
                    "Request ended before one complete JSON object was received.",
                )

            data.extend(chunk)
            if len(data) > MAX_REQUEST_BYTES:
                return None, _transport_error(
                    "validation_error",
                    "Request exceeds transport byte budget.",
                )

            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError as exc:
                if exc.end == len(data) and exc.reason == "unexpected end of data":
                    continue
                return None, _transport_error(
                    "validation_error",
                    "Request is not valid UTF-8.",
                )

            try:
                command = json.loads(text)
            except json.JSONDecodeError:
                continue

            if not isinstance(command, dict):
                return None, _transport_error(
                    "validation_error",
                    "Request must be one JSON object.",
                )
            return command, None

    def _encode_response(self, response):
        encoded = json.dumps(response, separators=(",", ":")).encode("utf-8")
        if len(encoded) <= MAX_RESPONSE_BYTES:
            return encoded
        return json.dumps(
            _transport_error(
                "internal_error",
                "Response exceeds transport byte budget.",
            ),
            separators=(",", ":"),
        ).encode("utf-8")

    def _handle_client(self, client):
        try:
            command, error = self._receive_request(client)
            response = error if error is not None else self.handle_command(command)
            client.sendall(self._encode_response(response))
        except Exception as e:
            print(f"[MCP] Client error: {e}")
            try:
                client.sendall(
                    self._encode_response(
                        _transport_error(
                            "internal_error",
                            "Transport failure while handling Blender command.",
                        )
                    )
                )
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

        op_id = str(command.get("op_id") or command.get("request_id") or uuid.uuid4())
        command["op_id"] = op_id
        command["request_id"] = op_id
        cmd_type = command.get("type", "")

        # BL-02 deadline tracking
        timeout = float(
            command.get("timeout") or command.get("timeout_seconds") or COMMAND_WAIT_TIMEOUT_SECONDS
        )
        deadline = time.monotonic() + timeout
        command["deadline"] = deadline

        # BL-01 / F02 / F11: Atomic reservation, fingerprinting, and admission check
        admitted, rejection = self.lifecycle.reserve_and_admit(
            cmd_type, op_id, command.get("params"), deadline
        )
        if not admitted:
            return rejection

        result_event = threading.Event()
        res_container = {"result": None, "op_id": op_id, "dispatched": False}

        try:
            self.command_queue.put_nowait(
                {
                    "command": command,
                    "event": result_event,
                    "container": res_container,
                    "op_id": op_id,
                    "deadline": deadline,
                    "cmd_type": cmd_type,
                }
            )
        except queue.Full:
            self.lifecycle.rollback_reservation(op_id, "Admission queue full")
            return {
                "status": "error",
                "kind": "rate_limited",
                "retryable": True,
                "op_id": op_id,
                "message": "Admission queue full. Backlog must drain; no work was enqueued.",
            }

        # Caller wait bound
        signaled = result_event.wait(timeout=timeout)
        if not signaled:
            # BL-02: started past deadline becomes uncertain; pending past deadline expired
            if res_container.get("dispatched"):
                self.lifecycle.record_uncertain(
                    op_id,
                    reason=f"Command '{cmd_type}' started execution but exceeded caller deadline of {timeout}s",
                    cmd_type=cmd_type,
                )
                return {
                    "status": "error",
                    "kind": "timeout_uncertain",
                    "retryable": True,
                    "op_id": op_id,
                    "message": (
                        f"Command '{cmd_type}' [{op_id}] timed out after {timeout}s while executing in Blender. "
                        "Operation state is uncertain; side effects may have occurred. "
                        "Call reconcile_operation before retrying."
                    ),
                    "receipt": self.lifecycle.get_receipt(op_id),
                }
            else:
                self.lifecycle.record_expired_pending(
                    op_id,
                    reason=f"Command '{cmd_type}' timed out while pending in admission queue",
                )
                return {
                    "status": "error",
                    "kind": "expired_pending",
                    "retryable": True,
                    "op_id": op_id,
                    "message": (
                        f"Command '{cmd_type}' [{op_id}] timed out after {timeout}s while pending in admission queue. "
                        "Execution was not started."
                    ),
                    "receipt": self.lifecycle.get_receipt(op_id),
                }

        return res_container["result"]

    def reconcile_operation(self, op_id: str, action: str = "query", **kwargs):
        """Reconcile receipt state of an operation, verifying postconditions on native state."""

        def _verifier(receipt):
            cmd = receipt.get("cmd_type", "")
            res = receipt.get("result")
            if isinstance(res, dict) and "result" in res:
                res = res["result"]

            # If the operation completed successfully in background with trusted outcome
            if (
                receipt.get("background_committed")
                and isinstance(res, dict)
                and bool(res.get("success", True))
            ):
                return {"verified": True, "note": "Trusted background completion"}

            # F10: Verify object creation postconditions
            if cmd in ("create_cube", "create_primitive", "create_cylinder", "create_sphere"):
                if isinstance(res, dict) and "name" in res:
                    obj_name = res["name"]
                    if hasattr(bpy.data, "objects") and obj_name in bpy.data.objects:
                        obj = bpy.data.objects[obj_name]
                        # Verify object has mesh data and matches expected type
                        if (
                            getattr(obj, "type", None) == "MESH"
                            and getattr(obj, "data", None) is not None
                        ):
                            return {
                                "verified": True,
                                "object_exists": True,
                                "object_name": obj_name,
                                "vertex_count": len(obj.data.vertices),
                            }
                return {"verified": False, "note": "Target object or mesh data not found"}

            # F10: Verify object transforms
            if cmd in ("object_move", "object_rotate", "object_scale", "transform_object"):
                if isinstance(res, dict) and "name" in res:
                    obj_name = res["name"]
                    if hasattr(bpy.data, "objects") and obj_name in bpy.data.objects:
                        return {"verified": True, "object_exists": True, "object_name": obj_name}
                return {
                    "verified": False,
                    "note": "Target object for transform not found or conclusive data missing",
                }

            # F10: Verify document save/open target matches expected filepath
            if cmd in ("document_save", "document_save_as", "document_open"):
                curr_fp = getattr(bpy.data, "filepath", "")
                if curr_fp and os.path.exists(curr_fp):
                    return {"verified": True, "filepath": curr_fp, "file_exists": True}
                return {"verified": False, "note": "Document filepath is empty or does not exist"}

            if cmd == "document_new":
                curr_fp = getattr(bpy.data, "filepath", "")
                return {
                    "verified": True,
                    "filepath": curr_fp,
                    "note": "document_new context verified",
                }

            return {"verified": False, "note": f"No native verifier available for command {cmd}"}

        return self.lifecycle.reconcile(op_id, action=action, native_verifier=_verifier)

    def operation_status(self, op_id: str, **kwargs):
        """Read-only query of receipt state for an operation ID."""
        receipt = self.lifecycle.get_receipt(op_id)
        if receipt is None:
            return {
                "status": "error",
                "kind": "not_found",
                "op_id": op_id,
                "message": f"No receipt found for operation [{op_id}].",
            }
        return {
            "status": "success",
            "op_id": op_id,
            "state": receipt.get("state"),
            "receipt": receipt,
        }

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
            for _ in range(MAX_COMMANDS_PER_TICK):
                try:
                    item = self.command_queue.get_nowait()
                    if not item:
                        continue
                    cmd, event, res = item["command"], item["event"], item["container"]
                    op_id = item.get("op_id") or cmd.get("op_id", "unknown")
                    deadline = item.get("deadline")
                    cmd_type = cmd.get("type", "")

                    # H05: Atomic transition PENDING -> IN_FLIGHT (checks deadline and predecessor uncertainty)
                    can_execute, start_rejection = self.lifecycle.try_start_dispatch(
                        op_id, cmd_type, deadline
                    )
                    if not can_execute:
                        res["result"] = start_rejection
                        event.set()
                        continue

                    # Mark dispatched in caller container
                    res["dispatched"] = True
                    self.addon_log(f"Processing command: {cmd_type} [{op_id}]")
                    try:
                        exec_res = self.execute_command(cmd)
                        res["result"] = exec_res
                        if isinstance(exec_res, dict) and exec_res.get("status") == "error":
                            self.lifecycle.record_failed(
                                op_id,
                                exec_res.get("message", "Error"),
                                result=exec_res,
                            )
                        else:
                            self.lifecycle.record_committed(op_id, exec_res)
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
                        self.lifecycle.record_failed(op_id, str(e))
                        res["result"] = {
                            "status": "error",
                            "message": f"Execution error: {e}",
                        }
                    finally:
                        event.set()
                        self.addon_log(f"Signaled event for {cmd_type}")
                except queue.Empty:
                    break
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
        methods: dict[str, Callable[..., Any]] = {
            # Runtime discovery (internal bridge command; not advertised as an MCP tool)
            "get_runtime_context": self.get_runtime_context,
            "reconcile_operation": self.reconcile_operation,
            "operation_status": self.operation_status,
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
            "unwrap_mesh": self.unwrap_mesh,
            "smart_project": self.smart_project,
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
            "clear_sculpt_mask": self.clear_sculpt_mask,
            "invert_sculpt_mask": self.invert_sculpt_mask,
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

            # F06: Check if business logic reported failure
            is_business_error = False
            error_msg = None
            if isinstance(result, dict):
                success_val = result.get("success")
                if success_val is not None and not success_val:
                    is_business_error = True
                    error_msg = result.get("error") or result.get("message") or "Operation failed"
                elif result.get("status") == "error":
                    is_business_error = True
                    error_msg = result.get("message") or result.get("error") or "Operation error"

            if is_business_error:
                return {
                    "status": "error",
                    "kind": "business_failure",
                    "retryable": False,
                    "message": error_msg,
                    "result": result,
                }

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
