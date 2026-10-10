"""Isolated Blender qualification for word/line animation, multi-stop gradient, emission, camera."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import bpy


def main():
    if "--" not in sys.argv or len(sys.argv[sys.argv.index("--") + 1 :]) != 1:
        raise ValueError("Exactly one output directory required")
    root = Path(sys.argv[sys.argv.index("--") + 1]).resolve(strict=True)
    if not root.is_dir() or list(root.iterdir()):
        raise ValueError("Output must be empty existing directory")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from blender_mcp_addon.tools.infographic_advanced import (
        animate_curve_reveal,
        animate_emission,
        animate_text_groups,
        configure_ortho_camera,
        gradient_with_stops,
        set_object_interpolation,
    )

    scene = bpy.context.scene
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 640
    scene.render.resolution_y = 360
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    words = animate_text_groups(
        text="AI Web to Real Machine",
        prefix="AUDIT_WORD",
        mode="word",
        start_frame=1,
        stagger=7,
        duration=15,
        size=0.36,
        location=(-2.6, 0.8, 0),
        color="#8DF6FF",
    )
    lines = animate_text_groups(
        text="Your AI.\nYour Machine.\nYour Control.",
        prefix="AUDIT_LINE",
        mode="line",
        start_frame=1,
        stagger=8,
        duration=15,
        size=0.27,
        location=(-2.2, -0.1, 0),
        color="#FFFFFF",
        line_height=0.48,
    )
    name = gradient_with_stops(
        "AUDIT_GRADIENT_4",
        stops=[
            {"position": 0, "color": "#143B8C"},
            {"position": 0.3, "color": "#0DDBF5"},
            {"position": 0.7, "color": "#8B47D6"},
            {"position": 1, "color": "#F05AFF"},
        ],
        emission_strength=1.5,
    )
    count = animate_emission(
        name,
        frames=[
            {"frame": 1, "strength": 0.1},
            {"frame": 20, "strength": 4},
            {"frame": 60, "strength": 1.5},
        ],
    )
    bpy.ops.mesh.primitive_plane_add(size=2, location=(0, -1.55, -0.2))
    obj = bpy.context.object
    obj.name = "AUDIT_GRADIENT_BAR"
    obj.scale = (2.8, 0.22, 1)
    obj.data.materials.append(bpy.data.materials[name])
    curve_data = bpy.data.curves.new("AUDIT_REVEAL_DATA", "CURVE")
    curve_data.dimensions = "3D"
    curve_data.bevel_depth = 0.02
    spline = curve_data.splines.new("POLY")
    spline.points.add(1)
    spline.points[0].co = (-2.5, -1.05, 0, 1)
    spline.points[1].co = (2.5, -1.05, 0, 1)
    curve_obj = bpy.data.objects.new("AUDIT_REVEAL", curve_data)
    scene.collection.objects.link(curve_obj)
    curve_data.materials.append(bpy.data.materials[name])
    reveal = animate_curve_reveal("AUDIT_REVEAL", start_frame=1, end_frame=60)
    bpy.data.objects[words[0]].location.x += 0.1
    bpy.data.objects[words[0]].keyframe_insert(data_path="location", frame=60)
    interpolation_count = set_object_interpolation(
        words[0], property_path="location", interpolation="LINEAR"
    )
    camera_data = bpy.data.cameras.new("AUDIT_CAMERA")
    camera = bpy.data.objects.new("AUDIT_CAMERA", camera_data)
    scene.collection.objects.link(camera)
    camera.location = (0, 0, 8)
    scene.camera = camera
    info = configure_ortho_camera("AUDIT_CAMERA", scale=6.5)
    scene.frame_start = 1
    scene.frame_end = 60
    scene.frame_set(60)
    bpy.ops.wm.save_as_mainfile(filepath=str(root / "extended.blend"))
    for frame in (1, 20, 60):
        scene.frame_set(frame)
        scene.render.filepath = str(root / f"frame-{frame:03d}.png")
        bpy.ops.render.render(write_still=True)
    print(
        "AUDIT_JSON:"
        + json.dumps(
            {
                "words": len(words),
                "lines": len(lines),
                "emission_keyframes": count,
                "curve_reveal": reveal,
                "interpolation_keys": interpolation_count,
                "camera": info,
                "blender": bpy.app.version_string,
            }
        )
    )


if __name__ == "__main__":
    main()
