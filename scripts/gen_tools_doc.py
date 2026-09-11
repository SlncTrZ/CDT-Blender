import importlib
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CATS = [
    # CDT fork: provider contract first (answered locally, never reach Blender).
    ("Provider", "blender_mcp_bridge.tools.provider", "get_provider_tools"),
    ("Scene & Diagnostics", "blender_mcp_bridge.tools.scene", "get_scene_tools"),
    ("Collections", "blender_mcp_bridge.tools.collections", "get_collection_tools"),
    ("Modeling", "blender_mcp_bridge.tools.modeling", "get_modeling_tools"),
    ("Materials", "blender_mcp_bridge.tools.materials", "get_material_tools"),
    ("Lighting & World", "blender_mcp_bridge.tools.lighting", "get_lighting_tools"),
    ("Camera", "blender_mcp_bridge.tools.camera", "get_camera_tools"),
    ("Animation", "blender_mcp_bridge.tools.animation", "get_animation_tools"),
    ("Rendering", "blender_mcp_bridge.tools.rendering", "get_rendering_tools"),
    ("History / Undo", "blender_mcp_bridge.tools.history", "get_history_tools"),
    # CDT fork: DCC interchange (Unreal Engine 5 lane).
    ("Interchange", "blender_mcp_bridge.tools.interchange", "get_interchange_tools"),
    ("3D-Print Preparation", "blender_mcp_bridge.tools.printing", "get_printing_tools"),
    ("Sculpting", "blender_mcp_bridge.tools.sculpting", "get_sculpting_tools"),
    # Answered locally from data/design-rules.json, not forwarded to Blender.
    ("Design Rules", "blender_mcp_bridge.tools.design_rules", "get_design_rule_tools"),
]


def params_str(t):
    props = t.inputSchema.get("properties", {})
    req = set(t.inputSchema.get("required", []))
    parts = []
    for p in props:
        parts.append(f"**{p}**" if p in req else p)
    return ", ".join(parts) if parts else "—"


lines = []
total = 0
toc = []
body = []
for cat, mod, fn in CATS:
    tools = getattr(importlib.import_module(mod), fn)()
    total += len(tools)
    anchor = (
        cat.lower()
        .replace(" & ", "--")
        .replace(" / ", "--")
        .replace(" ", "-")
        .replace("&", "")
        .replace("/", "")
    )
    toc.append(f"- [{cat}](#{anchor}) ({len(tools)})")
    body.append(f"\n## {cat}\n")
    body.append("| Tool | Description | Parameters (**bold** = required) |")
    body.append("|---|---|---|")
    for t in sorted(tools, key=lambda x: x.name):
        desc = " ".join(t.description.split()) if t.description else ""
        if len(desc) > 220:
            desc = desc[:217] + "..."
        body.append(f"| `{t.name}` | {desc} | {params_str(t)} |")

hdr = f"""# Bridge Tool Reference — {total} tools

Auto-generated from the bridge tool schemas in `blender_mcp_bridge/tools/` (the single source of truth
the MCP client sees). Regenerate after adding or changing a tool:

```bash
py scripts/gen_tools_doc.py   # or: uv run python scripts/gen_tools_doc.py
```

Every tool listed here has a matching handler in the Blender addon
(`blender_mcp_addon/server.py` dispatch table); a consistency check lives in the
generator and fails loudly on drift.

"""
out = hdr + "\n".join(toc) + "\n" + "\n".join(body) + "\n"
with open(f"{ROOT}/docs/tools.md", "w", encoding="utf-8") as f:
    f.write(out)
print("wrote docs/tools.md -", total, "tools")

# Drift check: every tool the bridge advertises must have an addon handler --
# except locally-answered tools (design rules + provider contract), which
# deliberately never reach the addon. Addon handlers without a bridge schema
# must be in QUARANTINED (discipline builders kept out of the CDT contract).
srv = open(f"{ROOT}/blender_mcp_addon/server.py", encoding="utf-8").read()
addon = set(re.findall(r'"([a-z0-9_]+)":\s*self\.', srv))
bridge = {t.name for cat, mod, fn in CATS for t in getattr(importlib.import_module(mod), fn)()}
from blender_mcp_bridge.tools.design_rules import DESIGN_RULE_HANDLERS  # noqa: E402
from blender_mcp_bridge.tools.provider import PROVIDER_HANDLERS  # noqa: E402

QUARANTINED = {
    # Architectural discipline builders (CDT_Engineer domains own these).
    "build_room_shell",
    "build_wall_segment",
    "build_wall_with_door",
    "build_column",
    "set_view",
    # MEP discipline builders.
    "build_pipe_run",
    "build_cable_tray",
    "add_tray_support",
}

bridge -= set(DESIGN_RULE_HANDLERS) | set(PROVIDER_HANDLERS)
unexplained_addon = (addon - bridge) - QUARANTINED
drift = unexplained_addon | (bridge - addon)
if drift:
    print("DRIFT:", sorted(unexplained_addon), sorted(bridge - addon))
    sys.exit(1)
print(
    "addon dispatch and bridge schemas are in sync:",
    len(bridge),
    "tools;",
    len(QUARANTINED),
    "quarantined discipline handlers (not advertised)",
)
