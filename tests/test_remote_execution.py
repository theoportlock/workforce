"""
End-to-end test: run workflow via workspace URL (remote execution).

This test boots the server, creates a simple graph on disk, constructs the
workspace URL, and then uses the Runner to connect via Socket.IO and execute
the workflow through the HTTP/Socket API. It validates that all nodes reach
the 'ran' status. The test also monkeypatches the Runner's server URL constant
so it connects to the dynamically discovered server port.
"""

import os
import time
import uuid
import tempfile
import requests
import networkx as nx

from workforce import utils, edit
from workforce.server import start_server
from workforce.run.client import Runner


def _wait_for(predicate, timeout=10.0, interval=0.1):
    start = time.time()
    while time.time() - start < timeout:
        val = predicate()
        if val:
            return val
        time.sleep(interval)
    return None


def _create_linear_graph(path):
    G = nx.DiGraph()
    a = str(uuid.uuid4())
    b = str(uuid.uuid4())
    c = str(uuid.uuid4())
    G.add_node(a, label="echo A", status="", x="0", y="0")
    G.add_node(b, label="echo B", status="", x="100", y="0")
    G.add_node(c, label="echo C", status="", x="200", y="0")
    G.add_edge(a, b, id=str(uuid.uuid4()))
    G.add_edge(b, c, id=str(uuid.uuid4()))
    edit.save_graph(G, path)
    return a, b, c


def test_remote_execution_via_workspace_url(tmp_path):
    # 1) Start server in background and discover host/port
    start_server(background=True)

    found = _wait_for(lambda: utils.find_running_server(), timeout=8.0)
    assert found is not None, "Server did not start"
    host, port = found
    base_server_url = f"http://{host}:{port}"

    # 2) Create a temporary workflow graph on disk
    workfile = tmp_path / "Workfile.graphml"
    a, b, c = _create_linear_graph(str(workfile))

    # 3) Compute workspace URL and create context with real path
    ws_id = utils.compute_workspace_id(str(workfile))
    ws_base = f"{base_server_url}/workspace/{ws_id}"

    # Ensure context is created with correct file path
    resp = requests.post(f"{ws_base}/client-connect", json={"workfile_path": str(workfile)})
    assert resp.status_code == 200

    try:
        # 4) Monkeypatch Runner's Socket.IO target to discovered server URL
        #    (Runner currently reads utils.WORKSPACE_SERVER_URL for Socket.IO connect)
        utils.WORKSPACE_SERVER_URL = base_server_url

        # 5) Start runner pointing at the workspace URL and wait for completion
        runner = Runner(ws_base, workspace_id=ws_id, workfile_path=str(workfile), wrapper="{}")

        # Run in a thread so we can poll graph state while it executes
        import threading
        t = threading.Thread(target=lambda: runner.start(initial_nodes=None), daemon=True)
        t.start()

        # 6) Poll graph until all nodes transition to 'ran'
        def all_ran():
            try:
                r = requests.get(f"{ws_base}/get-graph", timeout=1.5)
                if r.status_code != 200:
                    return False
                data = r.json()
                nodes = {n["id"]: n for n in data.get("nodes", [])}
                return (
                    a in nodes and b in nodes and c in nodes and
                    nodes[a].get("status") == "ran" and
                    nodes[b].get("status") == "ran" and
                    nodes[c].get("status") == "ran"
                )
            except Exception:
                return False

        assert _wait_for(all_ran, timeout=15.0), "Workflow did not complete via remote execution"

        # 7) Ensure runner thread exits
        t.join(timeout=2.0)
    finally:
        # Cleanup client context
        try:
            requests.post(f"{ws_base}/client-disconnect", json={})
        except Exception:
            pass
