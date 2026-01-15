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

    found = _wait_for(lambda: utils.get_running_server(), timeout=8.0)
    assert found is not None, "Server did not start"
    host, port, _pid = found
    base_server_url = f"http://{host}:{port}"

    def server_ready():
        try:
            r = requests.get(f"{base_server_url}/workspaces", timeout=1.0)
            return r.status_code == 200
        except Exception:
            return False

    assert _wait_for(server_ready, timeout=8.0), "Server HTTP endpoint not ready"

    # 2) Create a temporary workflow graph on disk
    workfile = tmp_path / "Workfile.graphml"
    a, b, c = _create_linear_graph(str(workfile))

    # 3) Register workspace and get URL
    registration = utils.register_workspace(base_server_url, str(workfile))
    ws_id = registration["workspace_id"]
    ws_base = registration["url"]

    try:
        # 4) Start runner pointing at the workspace URL
        #    (Runner will derive server root from workspace URL)
        runner = Runner(ws_base, workspace_id=ws_id, workfile_path=str(workfile), wrapper="{}")

        # Run in a thread so we can poll graph state while it executes
        import threading
        t = threading.Thread(target=lambda: runner.start(initial_nodes=None), daemon=True)
        t.start()

            # 6) Poll graph file until all nodes transition to 'ran'
            def all_ran_from_disk():
                try:
                    G = edit.load_graph(str(workfile))
                    return (
                        G.nodes[a].get("status") == "ran" and
                        G.nodes[b].get("status") == "ran" and
                        G.nodes[c].get("status") == "ran"
                    )
                except Exception:
                    return False

            assert _wait_for(all_ran_from_disk, timeout=15.0), "Workflow did not complete via remote execution"

        # 7) Ensure runner thread exits
        t.join(timeout=2.0)
    finally:
        try:
            utils.remove_workspace(base_server_url, ws_id)
        except Exception:
            pass
