import time
from pathlib import Path
import tempfile
import os

import pytest
import requests

from workforce.server import list_servers, start_server
from workforce import utils
from workforce.edit.graph import load_graph, save_graph


def _wait_for(predicate, timeout=8.0, interval=0.1):
    """Wait for predicate to return a truthy value, returning that value or None."""
    start = time.time()
    while time.time() - start < timeout:
        result = predicate()
        if result:
            return result
        time.sleep(interval)
    return None


def test_duplicate_server_prevention():
    """Test that attempting to start a second server when one is already running logs message and exits gracefully."""
    # Ensure a server is running
    result = utils.get_running_server()
    if not result:
        start_server(background=True)
        result = _wait_for(lambda: utils.get_running_server(), timeout=8.0)
        assert result is not None, "Server did not start"
    
    found_host, found_port, _pid = result
    
    # Verify server is accessible
    resp = requests.get(f"http://{found_host}:{found_port}/workspaces")
    assert resp.status_code == 200
    
    # Attempt to start another server - should detect existing and return early
    # This call should NOT create a second server on a different port
    start_server(background=True)
    
    # Give it a moment to potentially (incorrectly) start
    time.sleep(1.0)
    
    # Verify only one server is running by checking that the port didn't change
    new_result = utils.get_running_server()
    assert new_result is not None
    new_host, new_port, _new_pid = new_result
    
    # Should still be the same server
    assert new_port == found_port, f"New server started on port {new_port} instead of using existing server on {found_port}"
    
    # Verify no second server on adjacent ports
    for port in range(5000, 5100):
        if port == found_port:
            continue  # Skip the legitimate server port
        try:
            resp = requests.get(f"http://127.0.0.1:{port}/workspaces", timeout=0.5)
            if resp.status_code == 200 and "workspaces" in resp.json():
                raise AssertionError(f"Unexpected second server found on port {port}")
        except requests.exceptions.RequestException:
            pass  # Expected - no server on this port


def test_singleton_explicit_port():
    """Test singleton behavior with explicit port specification."""
    import subprocess
    import sys
    import os
    
    # Kill any existing servers
    pid_info = utils.get_running_server()
    if pid_info:
        try:
            import signal
            os.kill(pid_info[2], signal.SIGTERM if sys.platform != "win32" else signal.CTRL_C_EVENT)
            time.sleep(1.0)
        except Exception:
            pass
    
    # (a) Start first server on port 5050
    start_server(background=True, host="127.0.0.1", port=5050)
    result = _wait_for(lambda: utils.get_running_server(), timeout=8.0)
    assert result is not None, "First server did not start"
    first_host, first_port, first_pid = result
    assert first_port == 5050, f"Expected port 5050, got {first_port}"
    
    # Verify it's accessible
    resp = requests.get(f"http://127.0.0.1:5050/workspaces", timeout=2)
    assert resp.status_code == 200
    
    # (b) Attempt to start second server on same port - should detect and return early
    start_server(background=True, host="127.0.0.1", port=5050)
    time.sleep(1.0)
    
    # (c) Verify only one process exists on port 5050
    # Check that the PID hasn't changed
    new_result = utils.get_running_server()
    assert new_result is not None
    new_host, new_port, new_pid = new_result
    assert new_port == 5050, "Port changed unexpectedly"
    assert new_pid == first_pid, f"Second server process created (PID {new_pid}) instead of reusing existing (PID {first_pid})"


def test_server_add_registers_workspace(tmp_path):
    """Test that 'wf server add' registers a workspace and returns workspace metadata."""
    # Create a temporary workfile
    workfile_path = tmp_path / "test_workflow.graphml"
    G = load_graph(str(workfile_path))
    save_graph(G, str(workfile_path))
    
    # Resolve server (will find running or start new one)
    server_url = utils.resolve_server()
    
    # Register the workspace via register_workspace utility
    registration = utils.register_workspace(server_url, str(workfile_path))
    
    # Verify registration response
    assert "workspace_id" in registration, "Missing workspace_id in registration"
    assert "url" in registration, "Missing url in registration"
    assert "path" in registration, "Missing path in registration"
    
    workspace_id = registration["workspace_id"]
    assert workspace_id.startswith("ws_"), f"Invalid workspace_id format: {workspace_id}"
    
    # Verify the workspace URL is correct
    assert registration["url"].endswith(f"/workspace/{workspace_id}"), f"URL mismatch: {registration['url']}"
    
    # Verify workspace is listed in /workspaces
    resp = requests.get(f"{server_url}/workspaces")
    assert resp.status_code == 200
    workspaces = resp.json().get("workspaces", [])
    workspace_ids = [ws["workspace_id"] for ws in workspaces]
    assert workspace_id in workspace_ids, f"Workspace {workspace_id} not found in /workspaces"


def test_server_add_duplicate_registration(tmp_path):
    """Test that registering the same workspace twice returns same workspace_id."""
    # Create a temporary workfile
    workfile_path = tmp_path / "duplicate_test.graphml"
    G = load_graph(str(workfile_path))
    save_graph(G, str(workfile_path))
    
    # Resolve server
    server_url = utils.resolve_server()
    
    # Register the same workspace twice
    reg1 = utils.register_workspace(server_url, str(workfile_path))
    reg2 = utils.register_workspace(server_url, str(workfile_path))
    
    # Should get the same workspace_id both times
    assert reg1["workspace_id"] == reg2["workspace_id"], "Workspace ID changed on re-registration"
    assert reg1["url"] == reg2["url"], "URL changed on re-registration"


def test_server_rm_removes_workspace(tmp_path):
    """Test that 'wf server rm' removes a workspace from the server."""
    # Create a temporary workfile
    workfile_path = tmp_path / "removable.graphml"
    G = load_graph(str(workfile_path))
    save_graph(G, str(workfile_path))
    
    # Resolve server
    server_url = utils.resolve_server()
    
    # Register a workspace
    registration = utils.register_workspace(server_url, str(workfile_path))
    workspace_id = registration["workspace_id"]
    
    # Verify it's listed
    resp = requests.get(f"{server_url}/workspaces")
    workspaces = resp.json().get("workspaces", [])
    workspace_ids = [ws["workspace_id"] for ws in workspaces]
    assert workspace_id in workspace_ids
    
    # Remove the workspace
    result = utils.remove_workspace(server_url, workspace_id)
    assert result.get("status") == "removed" or "workspace_id" in result, f"Unexpected response: {result}"
    
    # Verify it's removed from /workspaces
    resp = requests.get(f"{server_url}/workspaces")
    workspaces = resp.json().get("workspaces", [])
    workspace_ids = [ws["workspace_id"] for ws in workspaces]
    assert workspace_id not in workspace_ids, f"Workspace {workspace_id} still in /workspaces after removal"


def test_server_rm_nonexistent_workspace():
    """Test that removing a non-existent workspace doesn't cause errors."""
    # Resolve server
    server_url = utils.resolve_server()
    
    # Try to remove a non-existent workspace
    # Should not raise, server should handle gracefully
    fake_ws_id = "ws_nonexistent123456"
    result = utils.remove_workspace(server_url, fake_ws_id)
    
    # Server should return success even for non-existent workspace
    assert result.get("status") == "removed" or "workspace_id" in result, f"Unexpected response: {result}"


def test_server_add_multiple_workspaces(tmp_path):
    """Test registering multiple different workspaces."""
    # Create multiple workfiles
    workfile1 = tmp_path / "workflow1.graphml"
    workfile2 = tmp_path / "workflow2.graphml"
    
    G1 = load_graph(str(workfile1))
    save_graph(G1, str(workfile1))
    
    G2 = load_graph(str(workfile2))
    save_graph(G2, str(workfile2))
    
    # Resolve server
    server_url = utils.resolve_server()
    
    # Register both workspaces
    reg1 = utils.register_workspace(server_url, str(workfile1))
    reg2 = utils.register_workspace(server_url, str(workfile2))
    
    # Should have different workspace IDs
    ws_id1 = reg1["workspace_id"]
    ws_id2 = reg2["workspace_id"]
    assert ws_id1 != ws_id2, "Different workfiles should have different workspace IDs"
    
    # Both should be listed
    resp = requests.get(f"{server_url}/workspaces")
    workspaces = resp.json().get("workspaces", [])
    workspace_ids = [ws["workspace_id"] for ws in workspaces]
    assert ws_id1 in workspace_ids
    assert ws_id2 in workspace_ids
    
    # Remove first one
    utils.remove_workspace(server_url, ws_id1)
    
    # Verify first is removed but second remains
    resp = requests.get(f"{server_url}/workspaces")
    workspaces = resp.json().get("workspaces", [])
    workspace_ids = [ws["workspace_id"] for ws in workspaces]
    assert ws_id1 not in workspace_ids
    assert ws_id2 in workspace_ids


def test_list_servers_with_explicit_url(tmp_path, monkeypatch, capsys):
    """list_servers should honor explicit server_url without PID checks."""
    workfile_path = tmp_path / "remote_ls.graphml"
    G = load_graph(str(workfile_path))
    save_graph(G, str(workfile_path))

    server_url = utils.resolve_server()
    registration = utils.register_workspace(server_url, str(workfile_path))
    workspace_id = registration["workspace_id"]

    # Simulate missing/stale PID file; list_servers must not rely on it when server_url is provided
    monkeypatch.setattr(utils, "_read_pid_file", lambda: None)

    list_servers(server_url=server_url)

    output = capsys.readouterr().out
    _, _, normalized_url = utils._normalize_server_url(server_url)
    assert workspace_id in output
    assert normalized_url in output