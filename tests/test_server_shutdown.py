import time
from pathlib import Path

import requests

from workforce.server import start_server
from workforce import utils


def _wait_for(predicate, timeout=8.0, interval=0.1):
    """Wait for predicate to return a truthy value, returning that value or None."""
    start = time.time()
    while time.time() - start < timeout:
        result = predicate()
        if result:
            return result
        time.sleep(interval)
    return None


def test_server_starts_and_context_lifecycle(tmp_path):
    """Test that server starts on dynamic port and contexts are created/destroyed on-demand."""
    workfile = tmp_path / "Workfile"
    workfile.touch()  # Create the file
    
    # Start server in background
    start_server(background=True)
    
    # Find the running server via pid tracking
    result = _wait_for(lambda: utils.get_running_server(), timeout=8.0)
    assert result is not None, "Server did not start"
    
    found_host, found_port, _pid = result
    
    # Compute workspace_id for this workfile
    workspace_id = utils.compute_workspace_id(str(workfile.resolve()))
    base_url = f"http://{found_host}:{found_port}/workspace/{workspace_id}"
    
    # Register a client for this workspace
    resp = requests.post(f"{base_url}/client-connect", json={"workfile_path": str(workfile)})
    assert resp.status_code == 200
    
    # Verify workspace context exists via diagnostics endpoint
    resp = requests.get(f"http://{found_host}:{found_port}/workspaces")
    workspaces = resp.json()["workspaces"]
    ws_ids = [ws["workspace_id"] for ws in workspaces]
    assert workspace_id in ws_ids
    
    # Disconnect the client
    resp = requests.post(f"{base_url}/client-disconnect", json={})
    assert resp.status_code == 200
    
    # Verify workspace context is destroyed (give it a moment)
    time.sleep(0.5)
    resp = requests.get(f"http://{found_host}:{found_port}/workspaces")
    workspaces = resp.json()["workspaces"]
    ws_ids = [ws["workspace_id"] for ws in workspaces]
    assert workspace_id not in ws_ids
    
    # Server should still be running (it's machine-wide, not killed after context closes)
    assert _wait_for(lambda: utils.get_running_server() is not None), "Server should still be running"


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
