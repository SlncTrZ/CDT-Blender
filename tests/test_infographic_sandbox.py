"""P0 sandbox safety and deterministic native launch contract."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from scripts.run_infographic_sandbox import run, validate_sandbox_path


def test_refuses_root_and_external_and_existing(tmp_path):
    root = tmp_path / "CDT-Blender" / "assets"
    root.mkdir(parents=True)
    with pytest.raises(ValueError):
        validate_sandbox_path(root, root)
    with pytest.raises(ValueError):
        validate_sandbox_path(root, tmp_path / "elsewhere")
    with pytest.raises(ValueError):
        validate_sandbox_path(root, root / "nested" / "job")
    existing = root / "existing"
    existing.mkdir()
    with pytest.raises(FileExistsError):
        validate_sandbox_path(root, existing)
    assert validate_sandbox_path(root, root / "new-job") == root / "new-job"


def test_run_uses_headless_factory_startup_without_loading_user_scene(tmp_path, monkeypatch):
    root = tmp_path / "CDT-Blender" / "assets"
    root.mkdir(parents=True)
    exe = tmp_path / "blender.exe"
    fixture = tmp_path / "fixture.py"
    exe.touch()
    fixture.touch()
    calls = []

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        (root / "test" / "infographic-sandbox.blend").write_bytes(b"blend")
        (root / "test" / "infographic-sandbox.png").write_bytes(b"png")
        return SimpleNamespace(returncode=0, stdout='AUDIT_JSON:{"blender":"4.5.3 LTS"}')

    monkeypatch.setattr("scripts.run_infographic_sandbox.subprocess.run", fake_run)
    run(exe, root, root / "test", fixture)
    assert len(calls) == 1
    argv, kwargs = calls[0]
    assert argv[1:3] == ["-b", "--factory-startup"]
    assert argv[3:6] == ["--python", str(fixture), "--"]
    assert kwargs["timeout"] == 150


@pytest.mark.parametrize(
    "stdout",
    [
        "Traceback: failed but Blender quit and returned 0",
        'AUDIT_JSON:{"blender":',
        'AUDIT_JSON:{"not_blender":"unknown"}',
    ],
)
def test_refuses_exit_zero_without_valid_fixture_receipt(tmp_path, monkeypatch, stdout):
    """Native Blender exit code alone cannot certify Python fixture success."""
    root = tmp_path / "CDT-Blender" / "assets"
    root.mkdir(parents=True)
    exe = tmp_path / "blender.exe"
    fixture = tmp_path / "fixture.py"
    exe.touch()
    fixture.touch()

    def fake_run(*args, **kwargs):
        output = root / "bad-receipt"
        (output / "infographic-sandbox.blend").write_bytes(b"blend")
        (output / "infographic-sandbox.png").write_bytes(b"png")
        return SimpleNamespace(returncode=0, stdout=stdout)

    monkeypatch.setattr("scripts.run_infographic_sandbox.subprocess.run", fake_run)
    with pytest.raises(RuntimeError, match="AUDIT_JSON"):
        run(exe, root, root / "bad-receipt", fixture)
    assert (root / "bad-receipt").exists()


def test_refuses_non_blender_binary(tmp_path):
    exe = tmp_path / "python.exe"
    exe.touch()
    with pytest.raises(ValueError):
        run(exe, tmp_path, tmp_path / "job", tmp_path / "fixture.py")
