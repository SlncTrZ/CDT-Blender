"""Curated compositor glow preset, with no arbitrary node graph execution."""

from __future__ import annotations

import math

import bpy  # type: ignore


def configure_glow(*, threshold: float = 1.0, quality: str = "HIGH") -> dict:
    """Replace an EMPTY compositor graph with Render Layers -> Glare -> Composite.

    Existing compositor nodes are never removed or overwritten. Caller should
    use a fresh scene or explicitly clear the graph through a separate workflow.
    """
    if (
        isinstance(threshold, bool)
        or not isinstance(threshold, (int, float))
        or not math.isfinite(threshold)
        or not 0 <= threshold <= 100
    ):
        raise ValueError("Threshold must be finite in 0..100")
    if quality not in {"HIGH", "MEDIUM", "LOW"}:
        raise ValueError("Unsupported glow quality")
    scene = bpy.context.scene
    if scene.use_nodes and scene.node_tree and len(scene.node_tree.nodes) > 0:
        raise ValueError("Compositor already has nodes; refusing destructive rewrite")
    scene.use_nodes = True
    tree = scene.node_tree
    if tree is None:
        raise ValueError("Compositor node tree unavailable")
    nodes, links = tree.nodes, tree.links
    layers = nodes.new("CompositorNodeRLayers")
    glare = nodes.new("CompositorNodeGlare")
    glare.glare_type = "FOG_GLOW"
    glare.quality = quality
    # Blender 4.5 uses an input socket, older builds may expose a property.
    if glare.inputs.get("Threshold") is not None:
        glare.inputs["Threshold"].default_value = float(threshold)
    elif hasattr(glare, "threshold"):
        glare.threshold = float(threshold)
    else:
        raise ValueError("Unsupported Blender compositor threshold API")
    composite = nodes.new("CompositorNodeComposite")
    links.new(layers.outputs["Image"], glare.inputs["Image"])
    links.new(glare.outputs["Image"], composite.inputs["Image"])
    return {"effect": "FOG_GLOW", "quality": quality, "threshold": threshold}
