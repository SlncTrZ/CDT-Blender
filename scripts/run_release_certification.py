#!/usr/bin/env python3
"""Release certification runner — CDT-Blender on Blender 4.5.3 LTS (native).
Wing: blender | Topic: release-certification | Updated: 2026-10-06 15:25

Dual-mode single file (Python stdlib only):

  Host mode (default):
      python scripts/run_release_certification.py [--out-dir DIR]
    Detects the exact git commit SHA + dirty state, locates the Blender 4.5.3
    LTS binary, launches it natively (Windows 11) with this same file as the
    Blender runner, then merges runner results with git/runtime identity into a
    structured JSON manifest under _private/evidence/<run>/manifest.json.

  Runner mode (invoked automatically by host mode — do not call manually):
      blender.exe --background --factory-startup \
          --python scripts/run_release_certification.py -- --blender-runner
    Executes the native bpy test suite:
      t1 document new/save, t2 primitive cube creation,
      t3 extrude with measured vertices, t4 STL export + SHA256 readback,
      t5 reconcile_operation — and writes runner_results.json.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform as _platform
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

RUNNER_FLAG = "--blender-runner"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REQUIRED_VERSION = (4, 5, 3)
EXPECTED_TEST_COUNT = 5

# Blender 4.5.3 LTS binary candidates (Windows 11 workstation .171 first).
BLENDER_CANDIDATES = [
    r"C:\Program Files\Blender Foundation\Blender 4.5\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 4.5.3\blender.exe",
]


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stdout.strip()


# --------------------------------------------------------------------------- #
# Host side
# --------------------------------------------------------------------------- #


def detect_source_state(root: Path) -> dict:
    """Exact commit SHA, short SHA, branch, dirty flag and dirty diff hash."""
    porcelain = _git(root, "status", "--porcelain")
    dirty = bool(porcelain.strip())
    return {
        "commit": _git(root, "rev-parse", "HEAD"),
        "commit_short": _git(root, "rev-parse", "--short", "HEAD"),
        "branch": _git(root, "branch", "--show-current"),
        "dirty": dirty,
        "dirty_diff_sha256": (
            hashlib.sha256(porcelain.encode("utf-8")).hexdigest() if dirty else None
        ),
    }


def find_blender() -> Path | None:
    for env_name in ("CDT_BLENDER_BIN", "BLENDER_BIN"):
        value = os.environ.get(env_name)
        if value and Path(value).is_file():
            return Path(value)
    for candidate in BLENDER_CANDIDATES:
        if Path(candidate).is_file():
            return Path(candidate)
    return None


def verify_blender(binary: Path) -> dict:
    proc = subprocess.run(
        [str(binary), "--version"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    out = (proc.stdout or "").strip()
    first_line = out.splitlines()[0] if out.splitlines() else ""
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", first_line)
    version_tuple = list(int(g) for g in match.groups()) if match else []
    return {"version_string": first_line, "version_tuple": version_tuple, "raw": out}


def compose_manifest(
    source: dict,
    version: dict,
    blender: Path,
    evidence: Path,
    command: list[str],
    exit_code: int,
    runner: dict,
) -> dict:
    runtime = runner.get("runtime", {})
    tests = runner.get("results", [])
    artifact = runner.get("artifact") or {}

    all_pass = len(tests) == EXPECTED_TEST_COUNT and all(
        t.get("status") == "pass" for t in tests
    )
    artifact_valid = (
        isinstance(artifact.get("size_bytes"), int)
        and artifact["size_bytes"] > 0
        and bool(SHA256_RE.fullmatch(str(artifact.get("sha256", ""))))
    )
    overall = "pass" if (all_pass and artifact_valid and exit_code == 0) else "fail"

    return {
        "schema_version": 2,
        "certification": "H15 release certification — Blender 4.5.3 LTS native (Windows 11)",
        "source": {
            "commit": source["commit"],
            "commit_short": source["commit_short"],
            "branch": source["branch"],
            "dirty": source["dirty"],
            "dirty_diff_sha256": source["dirty_diff_sha256"],
            "repo_root": str(_repo_root()),
        },
        "runtime": {
            "blender_version": version["version_string"],
            "version_tuple": version["version_tuple"],
            "binary": str(blender),
            "platform": "win32",
            "background": True,
            "blender_build_date": runtime.get("build_date"),
            "blender_build_hash": runtime.get("build_hash"),
            "blender_python": runtime.get("python_version"),
            "addon_version": runtime.get("addon_version"),
            "timestamp": time.time(),
            "timestamp_iso": datetime.now(timezone.utc).isoformat(),
        },
        "runner": {
            "script": "scripts/run_release_certification.py",
            "command": command,
            "log": str(evidence / "blender.log"),
            "exit_code": exit_code,
        },
        "tests": tests,
        "artifact": {
            "path": artifact.get("path"),
            "exists": bool(artifact.get("path") and Path(artifact["path"]).is_file()),
            "size_bytes": artifact.get("size_bytes"),
            "sha256": artifact.get("sha256"),
            "format": artifact.get("format"),
        },
        "overall_status": overall,
    }


def verify_manifest(manifest: dict) -> list[str]:
    """Independent host-side re-readback of the artifact and status fields."""
    problems: list[str] = []
    if manifest.get("overall_status") != "pass":
        problems.append("overall_status is not 'pass'")

    artifact = manifest.get("artifact", {})
    size = artifact.get("size_bytes")
    sha = artifact.get("sha256")
    if not (isinstance(size, int) and size > 0):
        problems.append(f"artifact size_bytes not positive: {size!r}")
    if not SHA256_RE.fullmatch(str(sha)):
        problems.append(f"artifact sha256 is not a real 64-hex digest: {sha!r}")

    path = artifact.get("path")
    if path and Path(path).is_file():
        recomputed = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        if recomputed != sha:
            problems.append(f"host readback sha256 mismatch: {recomputed} != {sha}")
        if Path(path).stat().st_size != size:
            problems.append(f"host readback size mismatch: {Path(path).stat().st_size} != {size}")
    else:
        problems.append(f"artifact path missing on disk: {path!r}")

    return problems


def host_main(argv: list[str]) -> int:
    root = _repo_root()

    out_dir: Path | None = None
    for i, arg in enumerate(argv):
        if arg == "--out-dir" and i + 1 < len(argv):
            out_dir = Path(argv[i + 1])

    source = detect_source_state(root)
    if not source["commit"]:
        print("ERROR: could not resolve git HEAD (is this a git repository?)")
        return 2

    blender = find_blender()
    if blender is None:
        print(
            "ERROR: Blender 4.5.3 LTS binary not found. "
            "Set CDT_BLENDER_BIN / BLENDER_BIN or install Blender 4.5 LTS."
        )
        return 2

    version = verify_blender(blender)
    if tuple(version["version_tuple"]) != REQUIRED_VERSION:
        print(
            f"ERROR: Blender version {version['version_string']} does not match "
            f"{'.'.join(map(str, REQUIRED_VERSION))} LTS."
        )
        return 2

    evidence = out_dir or (
        root / "_private" / "evidence" / f"release_certification_4.5.3_{source['commit_short']}"
    )
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / "runtime").mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env.update(
        {
            "CDT_CERT_EVIDENCE": str(evidence),
            "CDT_CERT_REPO": str(root),
            "CDT_CERT_COMMIT": source["commit"],
            "CDT_CERT_COMMIT_SHORT": source["commit_short"],
            "CDT_CERT_DIRTY": "true" if source["dirty"] else "false",
            "CDT_CERT_BLENDER_BIN": str(blender),
        }
    )

    command = [
        str(blender),
        "--background",
        "--factory-startup",
        "--python",
        str(Path(__file__).resolve()),
        "--",
        RUNNER_FLAG,
    ]

    log_path = evidence / "blender.log"
    with open(log_path, "w", encoding="utf-8", errors="replace") as log:
        proc = subprocess.run(
            command, env=env, stdout=log, stderr=subprocess.STDOUT, cwd=str(root), timeout=900
        )

    runner_file = evidence / "runner_results.json"
    if proc.returncode != 0 or not runner_file.is_file():
        print(
            f"ERROR: Blender runner failed (exit {proc.returncode}); "
            f"runner_results.json missing. See {log_path}"
        )
        return 1

    runner = json.loads(runner_file.read_text(encoding="utf-8"))
    manifest = compose_manifest(source, version, blender, evidence, command, proc.returncode, runner)

    manifest_path = evidence / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    problems = verify_manifest(manifest)

    print("=== CDT-Blender release certification ===")
    print(f"commit        : {source['commit']} (dirty={source['dirty']})")
    print(f"blender       : {version['version_string']} @ {blender}")
    print(f"manifest      : {manifest_path}")
    print(f"overall_status: {manifest['overall_status']}")
    for test in manifest["tests"]:
        print(f"  [{test['status']:4}] {test['id']}")
    artifact = manifest["artifact"]
    print(
        f"artifact      : size={artifact['size_bytes']} bytes "
        f"sha256={artifact['sha256']}"
    )
    if problems:
        print("VERIFY FAILED:")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    print("VERIFY: manifest overall_status=pass, artifact size>0, real sha256 — OK")
    return 0


# --------------------------------------------------------------------------- #
# Blender runner side (native bpy)
# --------------------------------------------------------------------------- #


def _decode(v):
    return v.decode("utf-8", "replace") if isinstance(v, bytes) else v


def run_native_suite(evidence: Path, repo: Path, commit: str, dirty: str) -> dict:
    import bpy  # noqa: F401  (only available inside Blender)

    sys.path.insert(0, str(repo))

    import blender_mcp_addon as addon_pkg
    from blender_mcp_addon.server import BlenderMCPServer
    from blender_mcp_addon.tools.document import DocumentTools
    from blender_mcp_addon.tools.modeling.operators import ModelingOperators
    from blender_mcp_addon.tools.modeling.primitives import ModelingPrimitives
    from blender_mcp_addon.tools.printing import PrintingTools

    runtime_dir = evidence / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    allow_roots = [str(runtime_dir)]
    state: dict = {}

    def require(condition: bool, message: str) -> None:
        if not condition:
            raise AssertionError(message)

    def t1_document_new_save() -> dict:
        tools = DocumentTools()
        new = tools.document_new(discard_unsaved=True)
        require(new.get("status") == "success", f"document_new failed: {new}")
        require(new.get("object_count") == 0, f"expected empty doc, got {new}")

        save_path = runtime_dir / "cert_document.blend"
        if save_path.exists():
            save_path.unlink()
        saved = tools.document_save_as(
            str(save_path), overwrite=False, _allow_roots=allow_roots
        )
        require(saved.get("status") == "success", f"document_save_as failed: {saved}")
        require(save_path.is_file() and save_path.stat().st_size > 0, "saved .blend missing/empty")

        info = tools.document_info()
        require(
            str(info.get("filepath", "")).lower().endswith("cert_document.blend"),
            f"unexpected filepath after save: {info.get('filepath')}",
        )
        return {
            "new_status": new.get("status"),
            "save_status": saved.get("status"),
            "filepath": info.get("filepath"),
            "is_saved": info.get("is_saved"),
            "object_count": info.get("object_count"),
        }

    def t2_primitive_cube() -> dict:
        prims = ModelingPrimitives()
        if "cert-cube" in bpy.data.objects:
            bpy.data.objects.remove(bpy.data.objects["cert-cube"], do_unlink=True)
        cube = prims.create_cube(location=[0.0, 0.0, 0.0], size=2.0, name="cert-cube")
        require(cube.get("success") is True, f"create_cube failed: {cube}")
        name = cube.get("name")
        require(name and name in bpy.data.objects, f"cube not present in scene: {name}")
        obj = bpy.data.objects[name]
        require(obj.type == "MESH", f"cube is not a mesh: {obj.type}")
        vertex_count = len(obj.data.vertices)
        require(vertex_count == 8, f"cube should have 8 vertices, got {vertex_count}")
        state["cube_name"] = name
        return {
            "name": name,
            "vertices": vertex_count,
            "dimensions": cube.get("dimensions"),
            "location": cube.get("location"),
        }

    def t3_extrude_vertices() -> dict:
        name = state["cube_name"]
        ops = ModelingOperators()
        ext = ops.extrude_mesh(name, mode="FACES", move=(0.0, 0.0, 1.0))
        require(ext.get("success") is True, f"extrude failed: {ext}")
        require(ext.get("verified") is True, "extrude result not verified")
        vertices_before = ext.get("vertices_before")
        vertices_after = ext.get("vertices_after")
        require(
            vertices_after > vertices_before,
            f"extrude added no vertices: {vertices_before} -> {vertices_after}",
        )
        measured = len(bpy.data.objects[name].data.vertices)
        require(
            measured == vertices_after,
            f"measured vertex readback mismatch: {measured} != {vertices_after}",
        )
        return {
            "vertices_before": vertices_before,
            "vertices_after": vertices_after,
            "measured_vertices": measured,
            "faces_before": ext.get("faces_before"),
            "faces_after": ext.get("faces_after"),
        }

    def t4_stl_export() -> dict:
        name = state["cube_name"]
        printing = PrintingTools()
        stl_path = runtime_dir / "cert_cube.stl"
        if stl_path.exists():
            stl_path.unlink()
        exp = printing.export_model(
            object_name=name,
            filepath=str(stl_path),
            format="STL",
            selection_only=True,
            _allow_roots=allow_roots,
        )
        require(exp.get("success") is True, f"STL export failed: {exp}")
        require(exp.get("verified") is True, "STL export not verified")
        size = exp.get("size_bytes")
        sha = exp.get("sha256")
        require(isinstance(size, int) and size > 0, f"STL size not positive: {size!r}")
        require(bool(SHA256_RE.fullmatch(str(sha))), f"STL sha256 invalid: {sha!r}")

        raw = stl_path.read_bytes()
        require(len(raw) == size, f"on-disk STL size {len(raw)} != reported {size}")
        recomputed = hashlib.sha256(raw).hexdigest()
        require(recomputed == sha, f"STL sha256 mismatch: {recomputed} != {sha}")

        state["artifact"] = {
            "path": str(stl_path),
            "size_bytes": size,
            "sha256": sha,
            "format": exp.get("artifact_format"),
        }
        return {
            "filepath": str(stl_path),
            "size_bytes": size,
            "sha256": sha,
            "format": exp.get("artifact_format"),
        }

    def t5_reconcile_operation() -> dict:
        name = state["cube_name"]
        server = BlenderMCPServer()
        lifecycle = server.lifecycle
        op_id = "manifest-cube-1"

        lifecycle.record_uncertain(op_id, "simulated caller timeout after dispatch", cmd_type="create_cube")
        lifecycle.record_committed(op_id, {"success": True, "name": name})
        require(op_id in lifecycle.get_uncertain_ops(), "op not uncertain before reconcile")

        resolved = server.reconcile_operation(op_id, action="resolve")
        require(resolved.get("status") == "success", f"reconcile failed: {resolved}")
        require(resolved.get("state") == "committed", f"reconcile did not commit: {resolved}")
        require(
            op_id not in resolved.get("uncertain_operations", []),
            "op still uncertain after reconcile",
        )

        queried = server.reconcile_operation(op_id, action="query")
        require(queried.get("state") == "committed", f"query after reconcile: {queried}")

        unknown = server.reconcile_operation("no-such-op", action="query")
        require(
            unknown.get("status") == "error" and unknown.get("state") == "unknown",
            f"unknown op did not report unknown: {unknown}",
        )
        return {
            "op_id": op_id,
            "resolved_state": resolved.get("state"),
            "query_state": queried.get("state"),
            "unknown_state": unknown.get("state"),
            "uncertain_after": resolved.get("uncertain_operations"),
        }

    order = [
        ("t1_document_new_save", t1_document_new_save),
        ("t2_primitive_cube", t2_primitive_cube),
        ("t3_extrude_vertices", t3_extrude_vertices),
        ("t4_stl_export", t4_stl_export),
        ("t5_reconcile_operation", t5_reconcile_operation),
    ]

    results = []
    for test_id, fn in order:
        started = time.perf_counter()
        try:
            details = fn()
            results.append(
                {
                    "id": test_id,
                    "status": "pass",
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                    "details": details,
                }
            )
        except Exception as exc:  # noqa: BLE001
            results.append(
                {
                    "id": test_id,
                    "status": "fail",
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                    "details": {"error": str(exc), "error_type": type(exc).__name__},
                }
            )

    runtime = {
        "blender_version": bpy.app.version_string,
        "version_tuple": list(bpy.app.version[:3]),
        "build_date": _decode(getattr(bpy.app, "build_date", "")),
        "build_hash": _decode(getattr(bpy.app, "build_hash", "")),
        "build_commit_date": _decode(getattr(bpy.app, "build_commit_date", "")),
        "background": bool(bpy.app.background),
        "platform": _platform.platform(),
        "python_version": sys.version.split()[0],
        "addon_version": list(getattr(addon_pkg, "bl_info", {}).get("version", [])),
        "commit": commit,
        "dirty": dirty,
    }

    return {"runtime": runtime, "results": results, "artifact": state.get("artifact")}


def runner_main() -> int:
    evidence = Path(os.environ["CDT_CERT_EVIDENCE"])
    repo = Path(os.environ["CDT_CERT_REPO"])
    commit = os.environ.get("CDT_CERT_COMMIT", "")
    dirty = os.environ.get("CDT_CERT_DIRTY", "false")

    try:
        payload = run_native_suite(evidence, repo, commit, dirty)
        (evidence / "runner_results.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
        )
        all_pass = len(payload["results"]) == EXPECTED_TEST_COUNT and all(
            t.get("status") == "pass" for t in payload["results"]
        )
        return 0 if all_pass else 1
    except Exception as exc:  # noqa: BLE001
        payload = {
            "error": str(exc),
            "error_type": type(exc).__name__,
            "runtime": {},
            "results": [],
            "artifact": None,
        }
        (evidence / "runner_results.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
        )
        print(f"RUNNER_ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


def main(argv: list[str]) -> int:
    if RUNNER_FLAG in argv:
        return runner_main()
    return host_main(argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
