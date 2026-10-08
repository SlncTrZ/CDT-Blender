# tests/test_sessions.py

import json
import os

from blender_mcp_bridge.sessions import BridgeSession, SessionMetadata, SessionRecorder


def test_session_lifecycle():
    path = "test_unit_session.json"
    print(f"1. Initializing Recorder with path: {path}")
    metadata = SessionMetadata(name="Test Session", description="Unit Test")
    recorder = SessionRecorder(path, metadata)

    print("2. Recording mock commands: 'create_cube', 'create_cylinder'...")
    recorder.record_command("create_cube", {"name": "Cube1"})
    recorder.record_command("create_cylinder", {"name": "Cyl1", "radius": 2.0})

    print(f"3. Verifying file existence: {path}")
    assert os.path.exists(path)

    print("4. Validating JSON structure and data integrity...")
    with open(path) as f:
        data = json.load(f)

    assert data["metadata"]["name"] == "Test Session"
    assert len(data["commands"]) == 2
    assert data["commands"][0]["tool"] == "create_cube"
    assert data["commands"][1]["arguments"]["radius"] == 2.0

    print("5. Testing BridgeSession.load() round-trip...")
    reloaded = BridgeSession.load(path)
    assert reloaded.metadata.name == "Test Session"
    assert len(reloaded.commands) == 2

    print("6. Cleaning up temporary test file...")
    os.remove(path)
    print("[PASS] Session Lifecycle Unit Test Passed!")


def test_playback_stops_on_error_or_uncertain(monkeypatch):
    import asyncio
    import types

    from blender_mcp_bridge.sessions import SessionPlayer

    player = SessionPlayer()
    calls = []

    class MockClient:
        async def call_tool_async(self, tool, args):
            calls.append(tool)
            return {"status": "error", "kind": "timeout_uncertain", "message": "unverified"}

    player._client = MockClient()
    cmd1 = types.SimpleNamespace(tool="object_move", arguments={}, description="")
    cmd2 = types.SimpleNamespace(tool="object_rotate", arguments={}, description="")
    session = types.SimpleNamespace(metadata=types.SimpleNamespace(name="probe", description=""))
    monkeypatch.setattr(player, "_select_branch", lambda *a: ([cmd1, cmd2], None, None))
    monkeypatch.setattr(player, "_resolve_params", lambda *a: ({}, []))
    monkeypatch.setattr(player, "_print_header", lambda *a: None)
    monkeypatch.setattr(player, "_print_summary", lambda *a: None)

    success_count, fail_count = asyncio.run(player.play(session))  # type: ignore[arg-type]
    # Must fail fast: only first command called, second command aborted
    assert len(calls) == 1
    assert calls[0] == "object_move"
    assert success_count == 0
    assert fail_count == 1


if __name__ == "__main__":
    test_session_lifecycle()
