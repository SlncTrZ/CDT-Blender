"""Blender headless native test of all seven public L2 server dispatch handlers.

Uses addon execute_command without opening network sockets or user documents.
A returned result is verified, saved to .blend, and rendered independently.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import bpy


def main() -> None:
    if "--" not in sys.argv or len(sys.argv[sys.argv.index("--") + 1 :]) != 2:
        raise ValueError("Expected sandbox output directory and RAQM asset directory")
    output, assets = (Path(p).resolve(strict=True) for p in sys.argv[sys.argv.index("--") + 1 :])
    if not output.is_dir() or list(output.iterdir()) or not assets.is_dir():
        raise ValueError("Sandbox must be an existing empty directory")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from blender_mcp_addon.server import BlenderMCPServer

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 720
    scene.render.resolution_y = 405
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.frame_end = 60
    source = output / "allowed.svg"
    source.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 60 30">'
        '<circle cx="15" cy="15" r="12" style="fill:#27BCCC"/>'
        '<path d="M27 7L57 15L27 23Z" style="fill:#9955EE"/></svg>',
        encoding="utf-8",
    )
    s = BlenderMCPServer()
    commands = [
        (
            "import_svg_curves",
            {
                "filepath": str(source),
                "prefix": "MCP_SVG",
                "target_width": 1.8,
                "location": (-2.9, -1.2, 0),
                "_allow_roots": [str(output)],
            },
        ),
        (
            "create_grease_strokes",
            {
                "name": "MCP_STROKES",
                "strokes": [[(-2, -0.55), (0, -0.75), (2, -0.55)]],
                "start_frame": 1,
                "end_frame": 60,
                "steps": 8,
            },
        ),
        (
            "create_filled_grease_tween",
            {
                "name": "MCP_FILLED",
                "start_strokes": [[(-0.5, -1.1), (0.0, -1.1), (-0.25, -0.65)]],
                "end_strokes": [[(-0.5, -1.1), (0.0, -1.1), (0.0, -0.55)]],
                "steps": 8,
                "end_frame": 60,
            },
        ),
        (
            "create_particle_preset",
            {
                "name": "MCP_RING",
                "mode": "RING",
                "count": 12,
                "radius": 0.05,
                "ring_radius": 0.45,
            },
        ),
        (
            "create_animated_particle_grid",
            {
                "name": "MCP_WAVE",
                "rows": 4,
                "columns": 8,
                "spacing": 0.15,
            },
        ),
        (
            "create_unicode_text",
            {
                "name": "MCP_UNICODE",
                "text": "Tiếng Việt · MCP",
                "size": 0.3,
                "location": (-2.5, 1.3, 0),
                "_allow_roots": [str(output)],
            },
        ),
        (
            "create_shaped_text_plane",
            {
                "name": "MCP_ARABIC",
                "png_path": str(assets / "arabic-raqm.png"),
                "_allow_roots": [str(assets)],
                "width": 3.0,
                "location": (0.7, 0.65, 0),
            },
        ),
    ]
    results = {}
    for idx, (command, params) in enumerate(commands):
        reply = s.execute_command(
            {
                "type": command,
                "params": params,
                "request_id": f"L2-{idx}",
            }
        )
        if reply.get("status") != "success":
            raise RuntimeError(f"Native MCP dispatch failed {command}: {reply}")
        results[command] = reply["result"]
    refused = s.execute_command(
        {
            "type": "create_animated_particle_grid",
            "params": {"name": "BAD_OVERBUDGET", "rows": 30, "columns": 30},
            "request_id": "L2-TYPED-REFUSAL",
        }
    )
    if not (
        refused.get("status") == "error"
        and refused.get("kind") == "validation_error"
        and refused.get("retryable") is False
    ):
        raise AssertionError(f"Native L2 typed validation refusal failed: {refused}")
    bpy.data.objects["MCP_RING"].location = (2, -0.75, 0)
    bpy.data.objects["MCP_WAVE"].location = (1.0, -1.45, 0)
    camera_data = bpy.data.cameras.new("MCP_CAMERA")
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = 6.5
    camera = bpy.data.objects.new("MCP_CAMERA", camera_data)
    scene.collection.objects.link(camera)
    camera.location = (0, 0, 8)
    scene.camera = camera
    scene.frame_set(60)
    bpy.ops.wm.save_as_mainfile(filepath=str(output / "mcp-infographic.blend"))
    frames = {}
    for frame in (1, 60):
        scene.frame_set(frame)
        png = output / f"mcp-frame-{frame:03d}.png"
        scene.render.filepath = str(png)
        bpy.ops.render.render(write_still=True)
        frames[str(frame)] = hashlib.sha256(png.read_bytes()).hexdigest()[:20]
    print(
        "AUDIT_JSON:"
        + json.dumps(
            {
                "blender": bpy.app.version_string,
                "tool_count": len(results),
                "tools": sorted(results),
                "frames": frames,
            }
        )
    )


if __name__ == "__main__":
    main()
