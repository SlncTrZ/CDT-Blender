"""Independent Blender background qualification of glyph animation and gradients."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import bpy


def main() -> None:
    if "--" not in sys.argv:
        raise ValueError("Expected -- output-dir")
    args = sys.argv[sys.argv.index("--") + 1 :]
    if len(args) != 1:
        raise ValueError("Expected exactly one output directory")
    output = Path(args[0]).resolve(strict=True)
    if not output.is_dir() or any(output.iterdir()):
        raise ValueError("Refusing nonempty output directory")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from blender_mcp_addon.tools.infographic_native import (
        animate_characters,
        configure_gradient_material,
    )

    scene = bpy.context.scene
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 800
    scene.render.resolution_y = 450
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = True
    scene.frame_start = 1
    scene.frame_end = 75
    names = animate_characters(
        text="AI -> GATEWAY",
        prefix="AUDIT_GLYPH",
        start_frame=1,
        stagger=3,
        duration=12,
        size=0.45,
        tracking=0.36,
        location=(-2.5, 0, 0),
        color="#70EFFF",
    )
    gradient = configure_gradient_material(
        "AUDIT_GRADIENT",
        start_color="#263CC8",
        end_color="#B54EFF",
        emission_strength=1.5,
    )
    bpy.ops.mesh.primitive_plane_add(size=2, location=(0, -1.3, -0.2))
    bar = bpy.context.object
    bar.name = "AUDIT_GRADIENT_CARD"
    bar.scale = (2.8, 0.24, 1)
    bar.data.materials.append(bpy.data.materials[gradient])
    camera_data = bpy.data.cameras.new("AUDIT_ORTHO")
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = 6.5
    camera = bpy.data.objects.new("AUDIT_ORTHO", camera_data)
    scene.collection.objects.link(camera)
    camera.location = (0, 0, 8)
    scene.camera = camera
    scene.frame_set(65)
    bpy.ops.wm.save_as_mainfile(filepath=str(output / "infographic-advanced.blend"))
    for frame in (1, 25, 65):
        scene.frame_set(frame)
        scene.render.filepath = str(output / f"infographic-frame-{frame:03d}.png")
        bpy.ops.render.render(write_still=True)
    print(
        "AUDIT_JSON:"
        + json.dumps(
            {
                "glyph_count": len(names),
                "gradient": gradient,
                "frame": scene.frame_current,
                "engine": scene.render.engine,
                "blender": bpy.app.version_string,
            }
        )
    )


if __name__ == "__main__":
    main()
