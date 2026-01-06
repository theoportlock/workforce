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
    
    # Find the running server via discovery
    def find_server():
        return utils.find_running_server()
    
    result = _wait_for(find_server, timeout=8.0)
    assert result is not None, "Server did not start"
    
    found_host, found_port = result
    
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
    assert _wait_for(lambda: utils.find_running_server() is not None), "Server should still be running"

