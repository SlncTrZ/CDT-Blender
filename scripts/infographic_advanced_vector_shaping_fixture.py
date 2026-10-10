"""Native 4.5 qualification of inline SVG style, filled GP tween, GN wave grid and shaped scripts."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import bpy

_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 90" width="120" height="90">
<rect x="3" y="5" width="112" height="78" style="fill:#223B79;stroke:#57E6FF;stroke-width:2"/>
<circle cx="30" cy="44" r="20" style="fill:#29C6DB;opacity:0.8"/>
<path d="M58 32L88 32L88 18L112 45L88 71L88 57L58 57Z" style="fill:#BB72FF"/>
</svg>"""


def run(output: Path, shared_assets: Path) -> dict:
    from blender_mcp_addon.tools.infographic_geometry_grid import create_animated_particle_grid
    from blender_mcp_addon.tools.infographic_grease_tween import create_filled_grease_tween
    from blender_mcp_addon.tools.infographic_shaped_plane import create_shaped_text_plane
    from blender_mcp_addon.tools.infographic_svg import import_svg_curves

    scene = bpy.context.scene
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 900
    scene.render.resolution_y = 506
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = True
    scene.frame_start = 1
    scene.frame_end = 60

    source_svg = output / "curated-vector.svg"
    source_svg.write_text(_SVG, encoding="utf-8")
    svg = import_svg_curves(
        str(source_svg),
        prefix="STYLE_VECTOR",
        allow_roots=[str(output)],
        target_width=1.9,
        location=(-3.6, -1.75, 0),
    )
    source_poly = [[(-0.9, -1.7), (-0.1, -1.7), (-0.5, -1.1)]]
    target_poly = [[(-0.9, -1.7), (-0.1, -1.7), (-0.1, -1.05)]]
    gp = create_filled_grease_tween(
        "GP_FILL_TWEEN",
        start_strokes=source_poly,
        end_strokes=target_poly,
        start_frame=1,
        end_frame=60,
        steps=12,
        fill_color="#AA5FFF",
        outline_color="#2BE1FF",
    )
    grid = create_animated_particle_grid(
        "GN_WAVEGRID",
        rows=8,
        columns=12,
        spacing=0.2,
        amplitude=0.42,
        particle_radius=0.047,
        color="#56E5F5",
        start_frame=1,
        end_frame=60,
    )
    bpy.data.objects[grid["object"]].location = (2.0, -1.1, 0.04)
    shapes = []
    for name, filename, y in (
        ("RTL_ARABIC", "arabic-raqm.png", 1.30),
        ("INDIC_HINDI", "hindi-raqm.png", 0.75),
    ):
        shapes.append(
            create_shaped_text_plane(
                name,
                png_path=str(shared_assets / filename),
                allow_roots=[str(shared_assets)],
                width=3.6,
                location=(-0.2, y, 0.0),
            )
        )

    camera_data = bpy.data.cameras.new("INFOGRAPHIC_ORTHO")
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = 8.1
    camera = bpy.data.objects.new("INFOGRAPHIC_ORTHO", camera_data)
    scene.collection.objects.link(camera)
    camera.location = (0, 0, 9)
    scene.camera = camera
    scene.frame_set(60)
    bpy.ops.wm.save_as_mainfile(filepath=str(output / "advanced-vector-shaping.blend"))
    frames = {}
    for frame in (1, 30, 60):
        scene.frame_set(frame)
        image = output / f"frame-{frame:03d}.png"
        scene.render.filepath = str(image)
        bpy.ops.render.render(write_still=True)
        frames[str(frame)] = hashlib.sha256(image.read_bytes()).hexdigest()[:20]
    return {
        "blender": bpy.app.version_string,
        "svg": svg,
        "gp_tween": gp,
        "gn_grid": grid,
        "shaped_text": shapes,
        "frame_hashes": frames,
    }


def main() -> None:
    if "--" not in sys.argv:
        raise ValueError("Expected -- output-dir shared-assets-dir")
    args = sys.argv[sys.argv.index("--") + 1 :]
    if len(args) != 2:
        raise ValueError("Expected exactly output and shared-assets directory")
    output = Path(args[0]).resolve(strict=True)
    assets = Path(args[1]).resolve(strict=True)
    if not output.is_dir() or list(output.iterdir()):
        raise ValueError("Output sandbox must be empty")
    if not assets.is_dir():
        raise ValueError("Missing shaped text assets")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    print("AUDIT_JSON:" + json.dumps(run(output, assets), ensure_ascii=False))


if __name__ == "__main__":
    main()
