import time
from pathlib import Path

import requests

from workforce.server import start_server
from workforce import utils


def _wait_for(predicate, timeout=8.0, interval=0.1):
    start = time.time()
    while time.time() - start < timeout:
        if predicate():
            return True
        time.sleep(interval)
    return False


def test_server_starts_and_context_lifecycle(tmp_path):
    """Test that server starts on fixed port and contexts are created/destroyed on-demand."""
    workfile = tmp_path / "Workfile"
    workfile.touch()  # Create the file
    
    # Start server in background
    start_server(background=True)
    
    port = utils.WORKSPACE_SERVER_PORT
    assert _wait_for(lambda: utils.is_port_in_use(port)), "Server did not start on port 5000"
    
    # Compute workspace_id for this workfile
    workspace_id = utils.compute_workspace_id(str(workfile.resolve()))
    base_url = utils.get_workspace_url(workspace_id)
    
    # Register a client for this workspace
    resp = requests.post(f"{base_url}/client-connect", json={"workfile_path": str(workfile)})
    assert resp.status_code == 200
    
    # Verify workspace context exists via diagnostics endpoint
    resp = requests.get("http://127.0.0.1:5000/workspaces")
    workspaces = resp.json()["workspaces"]
    ws_ids = [ws["workspace_id"] for ws in workspaces]
    assert workspace_id in ws_ids
    
    # Disconnect the client
    resp = requests.post(f"{base_url}/client-disconnect", json={})
    assert resp.status_code == 200
    
    # Verify workspace context is destroyed (give it a moment)
    time.sleep(0.5)
    resp = requests.get("http://127.0.0.1:5000/workspaces")
    workspaces = resp.json()["workspaces"]
    ws_ids = [ws["workspace_id"] for ws in workspaces]
    assert workspace_id not in ws_ids
    
    # Server should still be running (it's machine-wide, not killed after context closes)
    assert _wait_for(lambda: utils.is_port_in_use(port)), "Server should still be running"

