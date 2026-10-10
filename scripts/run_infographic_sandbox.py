"""Operator-run native Blender infographic fixture, isolated from user documents.

Example on Windows:
  python scripts/run_infographic_sandbox.py --blender "C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender.exe" --output-dir "C:\\Users\\me\\AppData\\Local\\CDT-Blender\\assets\\my-new-sandbox"

Will only create an empty output directory under CDT-Blender/assets; never deletes.
Does not load the CDT addon and does not bind a listening socket.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path


def validate_sandbox_path(base: Path, candidate: Path) -> Path:
    base = base.resolve(strict=True)
    candidate = candidate.resolve(strict=False)
    if not base.is_dir() or candidate == base or base not in candidate.parents:
        raise ValueError("Output directory must be a child of the CDT-Blender assets root")
    if candidate.exists():
        raise FileExistsError(f"Refusing to reuse or overwrite an existing sandbox: {candidate}")
    if candidate.parent != base:
        raise ValueError("Sandbox must be a direct child of the assets root")
    return candidate


def run(blender: Path, base: Path, output: Path, fixture: Path, timeout: int = 150) -> None:
    if not blender.is_file() or blender.name.lower() != "blender.exe":
        raise ValueError("An installed blender.exe must be supplied explicitly")
    if not fixture.is_file():
        raise FileNotFoundError(fixture)
    dest = validate_sandbox_path(base, output)
    dest.mkdir()
    try:
        result = subprocess.run(
            [str(blender), "-b", "--factory-startup", "--python", str(fixture), "--", str(dest)],
            cwd=str(base),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            check=False,
        )
        print(result.stdout[-4000:])
        if result.returncode != 0:
            raise RuntimeError(
                f"Blender exited with code {result.returncode}; fixture directory retained for inspection"
            )
        # Blender may exit 0 even when a Python script throws a traceback.
        # Require a parseable explicit fixture receipt before claiming PASS.
        receipts = [
            line.removeprefix("AUDIT_JSON:").strip()
            for line in result.stdout.splitlines()
            if line.startswith("AUDIT_JSON:")
        ]
        if len(receipts) != 1:
            raise RuntimeError("Missing or ambiguous AUDIT_JSON fixture receipt; refusing success")
        try:
            receipt = json.loads(receipts[0])
        except json.JSONDecodeError as exc:
            raise RuntimeError("Invalid AUDIT_JSON fixture receipt") from exc
        if not isinstance(receipt, dict) or receipt.get("blender") is None:
            raise RuntimeError("Unqualified AUDIT_JSON receipt")
        for expected in ("infographic-sandbox.blend", "infographic-sandbox.png"):
            output_file = dest / expected
            if not output_file.is_file() or output_file.stat().st_size == 0:
                raise RuntimeError(f"Sandbox artifact missing or empty: {output_file}")
    except Exception:
        # Never remove an output directory when a run fails; preserve evidence.
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--assets-root",
        type=Path,
        default=Path(os.environ.get("LOCALAPPDATA", "")) / "CDT-Blender" / "assets",
    )
    args = parser.parse_args()
    run(
        args.blender,
        args.assets_root,
        args.output_dir,
        Path(__file__).with_name("infographic_sandbox_fixture.py"),
    )


if __name__ == "__main__":
    main()
