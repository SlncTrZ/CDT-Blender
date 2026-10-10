"""Native sandbox qualification: animated chart, arc and material color/opacity."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import bpy


def main():
    if "--" not in sys.argv or len(sys.argv[sys.argv.index("--") + 1 :]) != 1:
        raise ValueError("One empty sandbox directory required")
    root = Path(sys.argv[sys.argv.index("--") + 1]).resolve(strict=True)
    if not root.is_dir() or list(root.iterdir()):
        raise ValueError("Refuse nonempty sandbox")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from blender_mcp_addon.tools.infographic_fx import configure_glow
    from blender_mcp_addon.tools.infographic_materials import (
        animate_material_property,
        update_material,
    )
    from blender_mcp_addon.tools.infographic_typography import animate_typewriter
    from blender_mcp_addon.tools.infographic_widgets import (
        create_bar_chart,
        create_progress_arc,
    )

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 800
    scene.render.resolution_y = 450
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.frame_start = 1
    scene.frame_end = 60
    typewriter = animate_typewriter(
        text="AI -> YOUR MACHINE",
        prefix="TITLE",
        start_frame=1,
        frames_per_character=2,
        size=0.24,
        tracking=0.025,
        location=(-2.8, 1.43, 0),
        color="#9FEFFF",
    )
    bars = create_bar_chart(
        prefix="METRIC",
        values=[0.2, 0.45, 0.7, 0.9, 0.55],
        colors=["#25B8E8", "#37D9EF", "#7777FF", "#BB66F9", "#F278C8"],
        origin=(-2.7, -1.1, 0),
        max_height=2.2,
        start_frame=1,
        duration=40,
        stagger=4,
    )
    arc = create_progress_arc(
        name="PROGRESS_80",
        progress=0.8,
        radius=0.85,
        location=(1.7, 0.15, 0),
        start_frame=1,
        end_frame=55,
    )
    mat_name = bars[0] + "_MAT"
    material_info = update_material(
        mat_name,
        scalars={"roughness": 0.35, "metallic": 0.12, "emission_strength": 2},
        colors={"base_color": "#14C8E8"},
    )
    keyframes = animate_material_property(
        mat_name,
        property_name="emission_color",
        keyframes=[
            {"frame": 1, "value": "#0A3455"},
            {"frame": 30, "value": "#55FFFF"},
            {"frame": 60, "value": "#B478FF"},
        ],
    )
    alpha_frames = animate_material_property(
        mat_name,
        property_name="alpha",
        keyframes=[
            {"frame": 1, "value": 0.1},
            {"frame": 30, "value": 0.8},
            {"frame": 60, "value": 1.0},
        ],
    )
    camera_data = bpy.data.cameras.new("ORTHO")
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = 6.6
    camera = bpy.data.objects.new("ORTHO", camera_data)
    scene.collection.objects.link(camera)
    camera.location = (0, 0, 8)
    scene.camera = camera
    glow = configure_glow(threshold=0.8, quality="HIGH")
    scene.frame_set(60)
    bpy.ops.wm.save_as_mainfile(filepath=str(root / "widgets.blend"))
    for frame in (1, 30, 60):
        scene.frame_set(frame)
        scene.render.filepath = str(root / f"frame-{frame:03d}.png")
        bpy.ops.render.render(write_still=True)
    print(
        "AUDIT_JSON:"
        + json.dumps(
            {
                "typewriter_glyphs": len(typewriter["objects"]),
                "bars": len(bars),
                "arc": arc,
                "glow": glow,
                "material": material_info,
                "emission_color_frames": keyframes["frames"],
                "alpha_frames": alpha_frames["frames"],
                "blender": bpy.app.version_string,
            }
        )
    )


if __name__ == "__main__":
    main()
