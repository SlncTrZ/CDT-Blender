"""Colour-conversion contract for the addon utility helper.

`hex_to_rgb` feeds every material/light/world colour path, and every caller
unpacks it as `(*rgb, 1.0)`. It previously returned the input unchanged for
anything not starting with '#', so `"FF0000"` produced a 7-element tuple and a
numeric input raised TypeError at the unpack site instead of failing here.
These tests pin the returned contract: always a normalized 3-float tuple.

`utils.py` is loaded directly rather than via the package, because importing
`blender_mcp_addon` runs `__init__` and pulls in every tool module (and thus
bpy/bmesh/mathutils). `hex_to_rgb` itself only needs the module-level `bpy`
import to resolve.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
UTILS_PATH = ROOT / "blender_mcp_addon" / "utils.py"

# The module-level `import bpy` must resolve before exec_module runs.
if "bpy" not in sys.modules:
    sys.modules["bpy"] = types.ModuleType("bpy")

_spec = importlib.util.spec_from_file_location("blender_mcp_addon.utils", UTILS_PATH)
assert _spec is not None and _spec.loader is not None
_utils = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_utils)

hex_to_rgb = _utils.hex_to_rgb


def test_hash_prefixed_hex_is_normalized():
    assert hex_to_rgb("#FF0000") == (1.0, 0.0, 0.0)
    assert hex_to_rgb("#00FF00") == (0.0, 1.0, 0.0)
    assert hex_to_rgb("#0000FF") == (0.0, 0.0, 1.0)
    assert hex_to_rgb("#FFFFFF") == (1.0, 1.0, 1.0)
    assert hex_to_rgb("#000000") == (0.0, 0.0, 0.0)


def test_hex_without_hash_prefix_is_accepted():
    """The old code returned the raw string here, breaking (*rgb, 1.0)."""
    assert hex_to_rgb("FF0000") == (1.0, 0.0, 0.0)
    assert hex_to_rgb("000000") == (0.0, 0.0, 0.0)


def test_result_unpacks_into_blender_four_component_colour():
    """Every caller does (*rgb, 1.0); that must always yield 4 components."""
    for spec_value in ("#FF8800", "FF8800", (1.0, 0.5, 0.0), [255, 136, 0]):
        rgba = (*hex_to_rgb(spec_value), 1.0)
        assert len(rgba) == 4


def test_already_numeric_rgb_sequence_passes_through_as_floats():
    assert hex_to_rgb((1, 0, 0)) == (1.0, 0.0, 0.0)
    assert hex_to_rgb([0.25, 0.5, 0.75]) == (0.25, 0.5, 0.75)


@pytest.mark.parametrize(
    "bad",
    [
        "not-a-colour",
        "#FFF",  # too short
        "#FF00",  # too short
        "#GGGGGG",  # non-hex digits
        "#FF00001",  # too long
        0.5,  # scalar: previously raised TypeError at the unpack site
        None,
        (1.0, 0.0),  # wrong channel count
        (1.0, 0.0, 0.0, 0.0),  # wrong channel count
    ],
)
def test_invalid_colour_fails_loudly_at_the_source(bad):
    """Invalid input must raise here, not silently corrupt colour or crash later."""
    with pytest.raises(ValueError):
        hex_to_rgb(bad)
