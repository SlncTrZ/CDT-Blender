"""Independent Blender 4.5+ qualification of safe SVG, GPv3, GN, Unicode."""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
from pathlib import Path

import bpy

_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="240" height="100" viewBox="0 0 240 100">
<g><rect x="4" y="5" width="225" height="88" fill="#123760" />
<circle cx="48" cy="50" r="25" fill="#54BFFF" />
<path d="M 100 48 L 145 48 L 145 30 L 185 55 L 145 80 L 145 62 L 100 62 Z" fill="#AE77FF" /></g>
</svg>"""


def main() -> None:
    if "--" not in sys.argv:
        raise RuntimeError("Expected -- output-dir")
    args = sys.argv[sys.argv.index("--") + 1 :]
    if len(args) != 1:
        raise RuntimeError("Expected one output directory")
    output = Path(args[0]).resolve(strict=True)
    if not output.is_dir() or list(output.iterdir()):
        raise ValueError("Output directory must exist and be empty")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from blender_mcp_addon.tools.infographic_geometry import create_particle_preset
    from blender_mcp_addon.tools.infographic_grease import create_grease_strokes
    from blender_mcp_addon.tools.infographic_svg import import_svg_curves
    from blender_mcp_addon.tools.infographic_unicode import create_unicode_text

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
    scene.frame_end = 60

    svg = output / "sanitized-source.svg"
    svg.write_text(_SVG, encoding="utf-8")
    imported = import_svg_curves(
        str(svg),
        prefix="VECTOR",
        allow_roots=[str(output)],
        target_width=1.9,
        location=(-2.7, -0.95, 0),
    )

    coords = [
        [(-2.9 + 5.8 * i / 35), (-1.36 + 0.13 * math.sin(4 * math.pi * i / 35)), 0]
        for i in range(36)
    ]
    gp = create_grease_strokes(
        "GP_STREAM",
        strokes=[coords],
        color="#23E5FD",
        radius=0.043,
        start_frame=1,
        end_frame=55,
        steps=9,
    )
    line = create_particle_preset(
        "GN_DATA",
        mode="LINE",
        count=33,
        radius=0.055,
        start=(-2.4, -0.25, 0.1),
        end=(1.3, -0.25, 0.1),
        color="#68AFFF",
    )
    ring = create_particle_preset(
        "GN_RING",
        mode="RING",
        count=21,
        radius=0.055,
        ring_radius=0.75,
        color="#BB85FF",
    )
    bpy.data.objects[ring["object"]].location = (2.0, 0.0, 0.1)
    win_fonts = Path(os.environ.get("WINDIR", "C:\\Windows")) / "Fonts"
    arial = win_fonts / "arial.ttf"
    text = create_unicode_text(
        "VN_TITLE",
        text="Kết nối AI · Tiếng Việt\nKiểm soát dữ liệu",
        size=0.34,
        line_spacing=1.36,
        location=(-2.8, 1.35, 0),
        color="#CBF7FF",
        tracking=1.04,
        font_path=str(arial) if arial.is_file() else None,
        allow_roots=[str(win_fonts)] if arial.is_file() else [],
    )
    cam_data = bpy.data.cameras.new("AUDIT_ORTHO")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 6.8
    camera = bpy.data.objects.new("AUDIT_ORTHO", cam_data)
    scene.collection.objects.link(camera)
    camera.location = (0, 0, 9)
    scene.camera = camera

    scene.frame_set(60)
    bpy.ops.wm.save_as_mainfile(filepath=str(output / "vector-gp-gn-unicode.blend"))
    hashes = {}
    for frame in (1, 30, 60):
        scene.frame_set(frame)
        png = output / f"frame-{frame:03d}.png"
        scene.render.filepath = str(png)
        bpy.ops.render.render(write_still=True)
        hashes[str(frame)] = hashlib.sha256(png.read_bytes()).hexdigest()[:20]
    print(
        "AUDIT_JSON:"
        + json.dumps(
            {
                "blender": bpy.app.version_string,
                "svg": imported,
                "gp": gp,
                "gn_line": line,
                "gn_ring": ring,
                "unicode": text,
                "frames": hashes,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
