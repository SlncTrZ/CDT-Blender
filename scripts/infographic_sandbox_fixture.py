"""Isolated Blender background fixture: no addon, sockets or user document interaction.

Called by: blender -b --factory-startup --python <this-file> -- <output-dir>
Output directory must already exist and be empty; fixtures never overwrite.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import bpy


def main() -> None:
    if "--" not in sys.argv:
        raise RuntimeError("Missing sandbox output directory")
    args = sys.argv[sys.argv.index("--") + 1 :]
    if len(args) != 1:
        raise RuntimeError("Expected one sandbox output directory")
    root = Path(args[0]).resolve(strict=True)
    if not root.is_dir() or list(root.iterdir()):
        raise RuntimeError("Sandbox directory must be empty")
    scene = bpy.context.scene
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 640
    scene.render.resolution_y = 360
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.frame_start = 1
    scene.frame_end = 30
    scene.render.film_transparent = True

    material = bpy.data.materials.new("AUDIT_Cyan")
    material.diffuse_color = (0.04, 0.83, 1, 1)
    material.use_nodes = True
    shader = material.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = material.diffuse_color
    shader.inputs["Emission Color"].default_value = (0.01, 0.65, 1, 1)
    shader.inputs["Emission Strength"].default_value = 2

    curve = bpy.data.curves.new("AUDIT_Path", "CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = 0.022
    curve.bevel_factor_end = 0.0
    curve.keyframe_insert(data_path="bevel_factor_end", frame=1)
    curve.bevel_factor_end = 1.0
    curve.keyframe_insert(data_path="bevel_factor_end", frame=30)
    spline = curve.splines.new("POLY")
    spline.points.add(2)
    for pt, co in zip(spline.points, [(-2, 0, 0, 1), (0, 0.4, 0, 1), (2, 0, 0, 1)], strict=True):
        pt.co = co
    obj = bpy.data.objects.new("AUDIT_Path", curve)
    scene.collection.objects.link(obj)
    obj.data.materials.append(material)
    obj.location.x = -0.15
    obj.keyframe_insert(data_path="location", frame=1)
    obj.location.x = 0.15
    obj.keyframe_insert(data_path="location", frame=30)
    for fc in obj.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

    font = bpy.data.curves.new("AUDIT_Label", "FONT")
    font.body = "AI  >  GATEWAY  >  PC"
    font.size = 0.43
    text = bpy.data.objects.new("AUDIT_Label", font)
    scene.collection.objects.link(text)
    text.location = (-2.35, -0.9, 0)
    text.data.materials.append(material)

    camera_data = bpy.data.cameras.new("AUDIT_Camera")
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = 6.0
    camera = bpy.data.objects.new("AUDIT_Camera", camera_data)
    scene.collection.objects.link(camera)
    camera.location = (0, 0, 8)
    camera.rotation_euler = (0, 0, 0)
    # Camera looks down local -Z; up direction is local Y.
    scene.camera = camera
    blend = root / "infographic-sandbox.blend"
    png = root / "infographic-sandbox.png"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    scene.render.filepath = str(png)
    bpy.ops.render.render(write_still=True)
    print(
        "AUDIT_JSON:"
        + json.dumps(
            {
                "blender": bpy.app.version_string,
                "engine": scene.render.engine,
                "objects": len(scene.objects),
                "filepath": str(blend),
                "render": str(png),
                "ortho_scale": camera_data.ortho_scale,
                "curve_reveal_animated": bool(curve.animation_data and curve.animation_data.action),
            }
        )
    )


if __name__ == "__main__":
    main()
