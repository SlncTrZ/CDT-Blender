"""Offline complex-script text asset shaping using Pillow RAQM (HarfBuzz + FriBidi).

This runs OUTSIDE Blender on a qualified host with libraqm and explicit font
files. The output is a transparent PNG, not editable glyph curves. It neither
downloads fonts nor accepts SVG/script input or external URLs.
"""

from __future__ import annotations

import argparse
import json
import math
import unicodedata
from pathlib import Path


def validate_request(
    text: str,
    *,
    direction: str,
    language: str,
    font_size: int,
    font_path: Path,
    output: Path,
    allow_roots: list[Path],
) -> dict:
    if not isinstance(text, str) or not 1 <= len(text) <= 512 or not text.strip():
        raise ValueError("Text must have 1..512 nonempty Unicode codepoints")
    normalized = unicodedata.normalize("NFC", text)
    if any(unicodedata.category(ch) in {"Cc", "Cs"} for ch in normalized):
        raise ValueError("Control or surrogate text characters refused")
    if direction not in {"rtl", "ltr"}:
        raise ValueError("Direction must be rtl or ltr")
    if language not in {"ar", "fa", "ur", "hi", "mr", "ne", "he"}:
        raise ValueError("Language unsupported by this shaping profile")
    if isinstance(font_size, bool) or not isinstance(font_size, int) or not 12 <= font_size <= 180:
        raise ValueError("Font size must be 12..180")
    if not allow_roots:
        raise ValueError("Explicit allow-roots required")
    roots = [p.resolve(strict=True) for p in allow_roots]
    font = font_path.resolve(strict=True)
    dest = output.resolve(strict=False)
    if not any(font == r or r in font.parents for r in roots):
        raise ValueError("Font must reside within an allowed root")
    if not any(r in dest.parents for r in roots):
        raise ValueError("Output must be inside an allowed root")
    if (
        font.suffix.lower() not in {".ttf", ".otf"}
        or not 1024 <= font.stat().st_size <= 16 * 1024 * 1024
    ):
        raise ValueError("Font must be a local bounded TTF/OTF file")
    if output.suffix.lower() != ".png" or dest.exists() or not dest.parent.is_dir():
        raise ValueError("Output must be a new PNG in an existing directory")
    return {"text": normalized, "font": font, "destination": dest}


def shape_to_png(
    text: str,
    *,
    direction: str,
    language: str,
    font_size: int,
    font_path: Path,
    output: Path,
    allow_roots: list[Path],
) -> dict:
    request = validate_request(
        text,
        direction=direction,
        language=language,
        font_size=font_size,
        font_path=font_path,
        output=output,
        allow_roots=allow_roots,
    )
    from PIL import Image, ImageDraw, ImageFont, features

    if not features.check("raqm"):
        raise RuntimeError("Pillow RAQM/HarfBuzz/FriBidi shaping engine unavailable")
    font = ImageFont.truetype(str(request["font"]), font_size, layout_engine=ImageFont.Layout.RAQM)
    draw_probe = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    drawer = ImageDraw.Draw(draw_probe)
    box = drawer.textbbox(
        (0, 0), request["text"], font=font, direction=direction, language=language
    )
    padding = 20
    width, height = (
        math.ceil(box[2] - box[0] + 2 * padding),
        math.ceil(box[3] - box[1] + 2 * padding),
    )
    if not 1 <= width <= 4096 or not 1 <= height <= 1024:
        raise ValueError("Shaped text exceeds output dimension limits")
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ImageDraw.Draw(image).text(
        (padding - box[0], padding - box[1]),
        request["text"],
        font=font,
        direction=direction,
        language=language,
        fill=(222, 245, 255, 255),
    )
    alpha = image.getchannel("A")
    if alpha.getbbox() is None:
        raise ValueError("Font rendered no visible text: missing glyph coverage or blank output")
    image.save(request["destination"], format="PNG")
    return {
        "profile": "offline-raqm-raster",
        "language": language,
        "direction": direction,
        "size": [width, height],
        "nonempty_alpha": True,
        "filepath": str(request["destination"]),
        "editable_vector": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", required=True)
    parser.add_argument(
        "--language", choices=["ar", "fa", "ur", "hi", "mr", "ne", "he"], required=True
    )
    parser.add_argument("--direction", choices=["rtl", "ltr"], required=True)
    parser.add_argument("--font", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--font-size", type=int, default=66)
    parser.add_argument("--allow-root", type=Path, action="append", required=True)
    args = parser.parse_args()
    print(
        "SHAPE_JSON:"
        + json.dumps(
            shape_to_png(
                args.text,
                direction=args.direction,
                language=args.language,
                font_size=args.font_size,
                font_path=args.font,
                output=args.output,
                allow_roots=args.allow_root,
            ),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
