# Bridge Tool Reference — 105 tools

Auto-generated from the bridge tool schemas in `blender_mcp_bridge/tools/` (the single source of truth
the MCP client sees). Regenerate after adding or changing a tool:

```bash
py scripts/gen_tools_doc.py   # or: uv run python scripts/gen_tools_doc.py
```

Every tool listed here has a matching handler in the Blender addon
(`blender_mcp_addon/server.py` dispatch table); a consistency check lives in the
generator and fails loudly on drift.

- [Provider](#provider) (3)
- [Document](#document) (6)
- [Object Query](#object-query) (3)
- [Organization](#organization) (1)
- [Scene & Diagnostics](#scene--diagnostics) (4)
- [Collections](#collections) (7)
- [Modeling](#modeling) (40)
- [Materials](#materials) (7)
- [Lighting & World](#lighting--world) (3)
- [Camera](#camera) (3)
- [Animation](#animation) (4)
- [Rendering](#rendering) (4)
- [History / Undo](#history--undo) (2)
- [Interchange](#interchange) (2)
- [3D-Print Preparation](#3d-print-preparation) (6)
- [Sculpting](#sculpting) (7)
- [Design Rules](#design-rules) (3)

## Provider

| Tool | Description | Parameters (**bold** = required) |
|---|---|---|
| `help` | Read-only operating contract for the blender provider: versions, authentication, capabilities and the complete usage guide. Call first; no side effects. | — |
| `system_capabilities` | Read-only machine-readable capability map with supported/unsupported modes and refusal reasons. Preflight before calling mutating tools. No side effects. | — |
| `system_status` | Read-only liveness report: provider versions, transport mode, guide availability and Blender addon reachability (socket probe only). No side effects. | — |

## Document

| Tool | Description | Parameters (**bold** = required) |
|---|---|---|
| `document_close` | Close the current logical document without terminating Blender by resetting to an empty unsaved file. | discard_unsaved |
| `document_info` | Read current Blender document identity, save state, scene and unit metadata. | — |
| `document_new` | Replace the current file with a new empty Blender document. | discard_unsaved |
| `document_open` | Open an existing .blend file inside the configured allow-roots. | **filepath**, discard_unsaved, load_ui |
| `document_save` | Save the current .blend file to its existing path; unsaved documents must use document_save_as. | — |
| `document_save_as` | Save the current Blender document to a .blend path inside the configured allow-roots. | **filepath**, overwrite, compress |

## Object Query

| Tool | Description | Parameters (**bold** = required) |
|---|---|---|
| `object_count` | Count objects in the active Blender scene, optionally filtered by object type or exact collection name; includes counts grouped by Blender object type. | type, collection |
| `object_get` | Get one object from the active Blender scene by its current exact Blender name, including common fields and Blender-specific extension data. | **name** |
| `object_list` | List objects in the active Blender scene in deterministic name order. Results are bounded and may be filtered by object type or collection. | type, collection, offset, limit |

## Organization

| Tool | Description | Parameters (**bold** = required) |
|---|---|---|
| `organization_list` | List Blender collections reachable from the active scene as common organizations. Results are deterministic, bounded, and include hierarchy and Blender visibility metadata. | offset, limit |

## Scene & Diagnostics

| Tool | Description | Parameters (**bold** = required) |
|---|---|---|
| `get_distance` | Measure the distance between two objects. | **object_a**, **object_b**, mode |
| `get_object_info` | Get detailed information about a specific object | **name** |
| `get_scene_info` | Get information about the current Blender scene | — |
| `get_viewport_screenshot` | Capture a screenshot of the 3D viewport. | max_size |

## Collections

| Tool | Description | Parameters (**bold** = required) |
|---|---|---|
| `create_collection` | Create a new collection in the scene | **name**, parent_collection |
| `duplicate_collection` | Duplicate an entire collection hierarchy including all nested objects and collections. | **collection_name**, new_name, target_parent, copy_contents_only, location_offset, rotation_offset |
| `get_collections` | Get hierarchy of all collections in the scene | — |
| `move_to_collection` | Move objects to a collection | object_names, pattern, collection_names, **target_collection**, keep_hierarchy, remove_original_collections |
| `remove_collection` | Remove a collection and optionally its contents. | name, pattern, delete_objects |
| `set_active_collection` | Set the active collection for new objects | **collection_name** |
| `set_collection_visibility` | Toggle visibility of a collection in the viewport and/or render. | **name**, hide_viewport, hide_render |

## Modeling

| Tool | Description | Parameters (**bold** = required) |
|---|---|---|
| `apply_all_modifiers` | Permanently apply all modifiers (like Booleans) on an object, baking their effects into the mesh data. | **object_name** |
| `apply_modifier` | ADDS and configures a modifier - despite the name it does NOT bake it. ALWAYS follow with apply_all_modifiers, or the modifier stays live and the next operation sees unmodified geometry. Verify with the vertex count, ... | **object_name**, **modifier_type**, name, target_objects, count, use_relative_offset, use_constant_offset, constant_offset_displace, relative_offset_displace, thickness, offset, ratio, decimate_type, mode, octree_depth, voxel_size, adaptivity, quad_method, ngon_method, min_vertices, width, segments, use_clamp_overlap, limit_method, angle_limit_deg, affect, harden_normals, miter_outer, levels, render_levels, use_axis, mirror_object, use_replace_original, factor, iterations, object_b, axis, angle_deg, steps, screw_offset, use_merge_vertices, merge_threshold, deform_method, deform_axis, limits, operation, solver, hide_cutter |
| `apply_transforms` | Bake scale, rotation, and/or location transforms into mesh vertex data. Crucial before boolean operations or joining objects with non-unit scale. | object_names, pattern, location, rotation, scale |
| `batch_transform` | Transform multiple existing objects with different positions/rotations/scales. | **transforms** |
| `boolean_operation` | Boolean operation between objects or collections. SLICE cuts a hole AND keeps the piece as a new object; operand_type='COLLECTION' uses all objects in a collection as cutters. CRITICAL: object_a must NOT be inside col... | **object_a**, **object_b**, **operation**, operand_type, solver, hide_cutter |
| `circular_array` | Create objects arranged in a circular/radial pattern (ring, circle, around a point). | **object_name**, **count**, **radius**, center, start_angle, axis, use_radial_rotation, collection, join_immediately, joined_name |
| `convert_to_mesh` | Convert a non-mesh object (like Text or Curve) to a Mesh object so it can be joined or modified. | **object_name** |
| `copy_modifier` | Copy a modifier from a source object to target objects. | **source_object**, target_objects, target_collection, **modifier_name** |
| `create_and_array` | Create a primitive with a linear array modifier. | **primitive_type**, **location**, name, collection, array_count, array_offset, scale, rotation, dimensions, radius, depth, vertices, major_radius, minor_radius, major_segments, minor_segments |
| `create_cone` | Create a cone mesh object or update an existing one if 'name' matches. | **location**, radius1, radius2, depth, scale, name, rotation, collection |
| `create_cube` | Create a cube mesh object or update an existing one if 'name' matches. TIP: Specify the 'collection' parameter directly here to save a step. | **location**, scale, size, dimensions, name, rotation, collection |
| `create_curve` | Create a curve for precise 2D/3D drafting: POLY/BEZIER/NURBS/PATH splines, or a mixed line + TRUE-ARC profile via 'segments' (exact arcs from center/radius/angles — use this for radius-gauge-style geometry, never tess... | **name**, spline_type, points, segments, cyclic, dimensions, fill_mode, extrude, bevel_depth, bevel_resolution, resolution_u, snap, location, collection |
| `create_cylinder` | Create a cylinder mesh object or update an existing one if 'name' matches. | **location**, radius, depth, dimensions, vertices, name, rotation, collection |
| `create_empty` | Create an Empty object, often used for instancing collections or as rigging roots. | **location**, name, empty_display_type, empty_display_size, instance_collection, collection, hide_viewport, hide_render |
| `create_icosphere` | Create an Ico Sphere mesh object (Icosphere) or update an existing one if 'name' matches. | **location**, radius, subdivisions, name, rotation, collection |
| `create_plane` | Create a plane mesh object or update an existing one if 'name' matches. | **location**, size, dimensions, name, rotation, collection |
| `create_polygon` | Create a flat polygon mesh from exact vertex coordinates, optionally extruded for thickness. For custom flat shapes needing precise corner positions. | **vertices**, **location**, extrude, taper, top_vertices, name, rotation, collection |
| `create_primitive` | Generic primitive creator: one call for cube, cylinder, sphere, icosphere, torus, plane, or cone. Prefer the dedicated create_* tools when they exist; this is the parametric catch-all. | **type**, **location**, scale, rotation, name, collection, size, radius, depth, vertices, subdivisions |
| `create_sphere` | Create a UV sphere mesh object or update an existing one if 'name' matches. | **location**, **radius**, scale, name, rotation, collection |
| `create_text` | Create 3D text (FONT object) or update existing one. Used for legends and labels. | **text**, **location**, name, size, extrude, align_x, font, offset, rotation, collection |
| `create_torus` | Create a torus mesh object or update an existing one if 'name' matches. | **location**, **major_radius**, **minor_radius**, major_segments, minor_segments, name, rotation, collection |
| `create_watertight_plate` | Build a WATERTIGHT extruded plate from a 2D outline with through-holes and engraved regions in one mesh, no booleans. Use INSTEAD of create_polygon + boolean_operation for printable flat parts with holes/text (boolean... | **name**, **outline**, **thickness**, holes, circle_holes, engrave_regions, engrave_depth, location, collection |
| `delete_object` | Delete object(s) by name or pattern (e.g. 'Test_*'). | object_name, pattern |
| `duplicate_object` | Duplicate an object — can also rename, move, and strip modifiers in the SAME call; prefer that over separate follow-up calls. | **object_name**, new_name, location, rotation, scale, collection, remove_modifiers, linked, hide_viewport, hide_render |
| `duplicate_selection` | Duplicate all currently selected objects with optional transformations. Useful for testing set_active_collection or batch duplication workflows. | location_offset, count, rotation_offset, scale, collection, remove_modifiers |
| `extract_sketch` | Reverse of create_curve: dump sketched CURVE and grease-pencil geometry as world-space JSON (control points, cyclic flags, Bezier handles, stroke points). Read-only. Feed the result to scripts/sketch_to_session.py to ... | pattern, include_handles |
| `extrude_mesh` | Extrude mesh geometry (vertices, edges, or faces). PRO TIP: Use 'filter_normal' (e.g. [0,0,1] for top) to extrude specific parts of an object instead of the whole thing. | **object_name**, mode, move, filter_normal, angle_threshold, use_selection |
| `inset_faces` | Inset faces of a mesh (great for creating walls from floors). PRO TIP: Use 'filter_normal' to only inset specific faces (like the top face). | **object_name**, **thickness**, depth, filter_normal, angle_threshold, use_selection |
| `invert_mesh_selection` | Invert selection of mesh components (verts/edges/faces) inside an object. | **object_name** |
| `join_objects` | Merge multiple objects into one (pass object_names, or omit to join the current selection). Good for consolidating repetitive elements like fins or windows. | object_names, active_object, new_name |
| `random_distribute` | Randomly distribute copies of an object within a ring or volume, centred on 'center' (or the source object's location if omitted — not the world origin). | **object_name**, **count**, **min_distance**, **max_distance**, center, z_position, seed |
| `remove_modifier` | Remove a modifier from an object | **object_name**, **modifier_name** |
| `select_by_collection` | Select all objects within a specific collection. | **collection_names**, extend |
| `select_by_pattern` | Select objects by name pattern. AVOID select-then-assign workflows: pass 'pattern' directly to create_material / assign_material / batch_transform instead, in one call. | **pattern**, extend |
| `select_objects` | Select objects by name. AVOID select-then-assign workflows: most tools (e.g. create_material) accept object names directly in one call. | **object_names**, active_object |
| `separate_loose_parts` | Split one mesh's disconnected shells into separate objects. A boolean that cuts a part into pieces leaves ONE object holding several shells, and delete_object works per object - so use this when the pieces must be han... | **object_name**, prefix |
| `set_object_dimensions` | Set exact world-space bounding box dimensions for an object, in meters. Rotation-safe: works correctly regardless of the object's current rotation. | **object_name**, **x**, **y**, **z** |
| `set_object_visibility` | Toggle or set visibility of an object in the viewport and/or render. SMART TOGGLE: If 'hide_viewport' and 'hide_render' are both omitted, the current visibility state will be flipped. | **object_name**, hide_viewport, hide_render |
| `shear_mesh` | Shear mesh geometry along an axis (useful for sloped roofs). PRO TIP: Use 'filter_normal' (e.g. [0,0,1]) to shear only the top faces. | **object_name**, **value**, axis, orient_axis, filter_normal, angle_threshold |
| `transform_object` | Transform an existing object's position, rotation, or scale. Supports bulk transformation via pattern. | object_name, pattern, location, location_offset, rotation, rotation_offset, scale, hide_viewport, hide_render |

## Materials

| Tool | Description | Parameters (**bold** = required) |
|---|---|---|
| `add_shader_node` | Add a shader node to a material's node tree. | **material_name**, **node_type**, **location** |
| `assign_builtin_texture` | Apply a Blender built-in procedural texture to a material. | **material_name**, **texture_type** |
| `assign_material` | Assign an existing material. RATE LIMIT WARNING: Use 'pattern' or 'collection' directly here to assign to many objects in ONE TURN. Avoid using 'select_by_pattern' first as it doubles the API calls. | **material_name**, object_names, pattern, collection, slot_index |
| `assign_texture_map` | Load an image and assign it to a material slot (Base Color, Roughness, Normal, etc.). Supports auto-creation of Normal Map nodes. | **material_name**, **image_path**, map_type |
| `connect_shader_nodes` | Connect two shader nodes. | **material_name**, **from_node**, **from_socket**, **to_node**, **to_socket** |
| `create_material` | POWER TIP: Use 'pattern' or 'collection' directly here to create AND assign in ONE TURN. This is much faster and avoids rate limits compared to sequential selection-assignment workflows. | **name**, preset, base_color, roughness, metallic, transmission, ior, emission_color, emission_strength, alpha, object_names, pattern, collection, slot_index |
| `set_material_properties` | Modify properties of an existing material. | **material_name**, base_color, metallic, roughness, emission_color, emission_strength, alpha, transmission |

## Lighting & World

| Tool | Description | Parameters (**bold** = required) |
|---|---|---|
| `configure_light` | Modify an existing light's properties (energy, color, rotation, angle, size). | **light_name**, energy, color, rotation, angle, size |
| `create_light` | Create light (POINT, SUN, SPOT, AREA) | **name**, **type**, **location**, energy, color, angle, size |
| `set_world_background` | Set the world background to a solid color, a procedural sky, or an HDRI environment image. | **mode**, color, strength, image_path, rotation_z |

## Camera

| Tool | Description | Parameters (**bold** = required) |
|---|---|---|
| `camera_look_at` | Point a camera at a target location. | **camera_name**, **target_location** |
| `create_camera` | Create camera | **name**, **location**, rotation, lens, type |
| `set_active_camera` | Set the active camera for the scene. | **camera_name** |

## Animation

| Tool | Description | Parameters (**bold** = required) |
|---|---|---|
| `get_keyframes` | Get all keyframes for an object. | **object_name** |
| `play_animation` | Play or stop animation playback. | play |
| `set_keyframe` | Set a keyframe for an object property. | **object_name**, **property_path**, **frame**, **value** |
| `set_timeline_range` | Set the timeline range for animation. | **start_frame**, **end_frame**, current_frame |

## Rendering

| Tool | Description | Parameters (**bold** = required) |
|---|---|---|
| `configure_render_settings` | Configure render settings. | engine, samples, resolution_x, resolution_y |
| `generate_views` | Render orthographic top/front/side/iso previews of the scene in one call. Temporary cameras and lights are framed automatically from the scene's bounding box and removed afterwards, so no camera/light/render commands ... | views, prefix, output_dir, samples, resolution, margin, engine, objects |
| `render_animation` | Render an animation sequence. | start_frame, end_frame, output_dir |
| `render_frame` | Render the current frame. | output_path |

## History / Undo

| Tool | Description | Parameters (**bold** = required) |
|---|---|---|
| `redo` | Redo the last undone action in Blender | — |
| `undo` | Undo the last action in Blender | — |

## Interchange

| Tool | Description | Parameters (**bold** = required) |
|---|---|---|
| `export_fbx` | Export the scene (or selection) to FBX for DCC interchange (Unreal Engine 5 lane). Units are meters; axis convention is explicit — UE5 imports Y-forward/Z-up via its own preset, so export Blender-native -Z-forward/Y-u... | **filepath**, export_selected, apply_scale, bake_space_transform |
| `export_gltf` | Export the scene (or selection) to glTF 2.0 (.glb/.gltf) for DCC interchange. glTF is Y-up; Blender converts on export. | **filepath**, export_selected, export_materials |

## 3D-Print Preparation

| Tool | Description | Parameters (**bold** = required) |
|---|---|---|
| `apply_voxel_remesh` | Fuse multiple overlapping geometry parts into a single watertight manifold volume using a Voxel Remesh operation. Note: This operation can be lossy and deletes original UV maps. | **object_name**, voxel_size, adaptivity, clean_geometry |
| `check_mesh_for_printing` | Analyze a mesh object's topology for 3D printing readiness. Checks for boundary edges (holes), non-manifold edges (T-junctions), degenerate edges/faces (zero size), and computes mesh volume. | **object_name** |
| `export_model` | Export the specified object or the entire selection to standard formats (STL or 3MF). 3MF preserves materials and colors for multi-color printing. Relative paths are resolved against the BLENDER_ASSETS_DIR folder. | object_name, filepath, format, selection_only |
| `import_model` | Import a 3D model file (STL, OBJ, or FBX) into the scene and select it. Relative paths are resolved against the BLENDER_ASSETS_DIR folder. | **filepath** |
| `repair_mesh` | Attempt automated non-destructive mesh cleanup and repairs (merge double vertices, fill holes, and recalculate face normals outwards). | **object_name**, merge_distance, recalculate_normals |
| `set_scene_units` | Configure the scene measurement units and scaling. This is crucial for 3D printing because slicers expect absolute millimeter dimensions while Blender defaults to meters. | system, length_unit, scale |

## Sculpting

| Tool | Description | Parameters (**bold** = required) |
|---|---|---|
| `apply_sculpt_smooth` | Apply Laplacian smoothing to an entire mesh to round out hard edges and surface bumps. Works in Object Mode — no live viewport needed. Use after voxel remesh to soften blocky artifacts. | **object_name**, iterations, factor |
| `enter_sculpt_mode` | Switch a mesh object into Blender's Sculpt Mode. Must be called before set_dyntopo or symmetrize_mesh. | **object_name** |
| `exit_sculpt_mode` | Exit Sculpt Mode and return the active object to Object Mode. | — |
| `sculpt_grab` | Grab-brush style sculpt: move vertices near a 3D location by an offset vector. Uses smooth cosine falloff: vertices at the center move the full offset, vertices at the radius edge are barely moved. Use this to pull a ... | **object_name**, **location**, **offset**, radius |
| `sculpt_inflate` | Inflate or deflate a mesh by displacing all vertices along their surface normals. Positive distance = expand outward like a balloon. Negative distance = shrink inward. Use mask_below_z to protect the flat base (e.g. m... | **object_name**, distance, mask_below_z |
| `set_dyntopo` | Enable or disable Dynamic Topology (Dyntopo) in Sculpt Mode. Dyntopo automatically subdivides or merges polygons as you sculpt, allowing unlimited resolution in specific areas. Requires enter_sculpt_mode to be called ... | enabled, detail_size, constant_detail |
| `symmetrize_mesh` | Mirror mesh geometry across an axis so both sides are perfectly symmetric. The source side overwrites the mirror side. POSITIVE_X copies the +X half to the -X side. Automatically enters and exits Sculpt Mode. | **object_name**, direction |

## Design Rules

| Tool | Description | Parameters (**bold** = required) |
|---|---|---|
| `check_design` | Look up 3D-printing design rules bearing on a part you are about to model, described in plain language (e.g. 'a snap-fit enclosure lid with 2mm walls and pin joints'). Returns wall minimums, clearances, overhang limit... | **description**, limit |
| `get_design_rules` | Filter the 3D-printing design rules by keyword, topic or unit. Prefer check_design when you can describe the part in prose. Consult this BEFORE generating geometry, not after -- these constraints are cheap to honour w... | keyword, topic, unit, measured_only, limit |
| `list_design_topics` | List the design-rule topics with how many rules each holds and how many carry a stated dimension. Useful for judging whether the knowledge base can answer a question before asking it. | — |
