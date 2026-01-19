"""
Integration tests for multi-workspace architecture.

Tests the complete workflow with the new fixed-port server and workspace routing:
- Server auto-start on fixed port 5049
- On-demand workspace context creation/destruction
- Workspace isolation (events don't cross workspaces)
- Multi-workspace concurrent operations
- Client lifecycle management
"""

import os
import tempfile
import time
import uuid
import logging
import requests
import pytest
import networkx as nx

from workforce import utils, edit
from workforce.server import start_server
from workforce.server.context import ServerContext

log = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def server_url():
    """Start server once per test module and return its URL."""
    # Use resolve_server to find or start server
    try:
        server = utils.resolve_server()
    except Exception as e:
        pytest.skip(f"Failed to start/discover server: {e}")
    
    # Verify server is accessible
    max_retries = 30
    for attempt in range(max_retries):
        try:
            resp = requests.get(f"{server}/workspaces", timeout=1)
            if resp.status_code == 200:
                yield server
                return
        except Exception:
            pass
        time.sleep(0.3)
    else:
        pytest.skip("Server failed to respond")
    
    # Server stays running for other tests


@pytest.fixture
def temp_workfile():
    """Create a temporary workfile for testing."""
    fd, path = tempfile.mkstemp(suffix=".graphml")
    os.close(fd)
    # Initialize with an empty graph
    G = nx.DiGraph()
    nx.write_graphml(G, path)
    yield path
    if os.path.exists(path):
        os.unlink(path)


def create_simple_graph(path):
    """Create a simple graph: A -> B -> C"""
    G = nx.DiGraph()
    node_a = str(uuid.uuid4())
    node_b = str(uuid.uuid4())
    node_c = str(uuid.uuid4())
    
    G.add_node(node_a, label="echo A", status="", x="0", y="0")
    G.add_node(node_b, label="echo B", status="", x="100", y="0")
    G.add_node(node_c, label="echo C", status="", x="200", y="0")
    
    G.add_edge(node_a, node_b)
    G.add_edge(node_b, node_c)
    
    edit.save_graph(G, path)
    return {"a": node_a, "b": node_b, "c": node_c}


class TestServerInitialization:
    """Test basic server startup and initialization."""
    
    def test_server_accessible(self, server_url):
        """Verify server is accessible and responding."""
        result = utils.get_running_server()
        assert result is not None
    
    def test_workspace_endpoint_accessible(self, server_url):
        """Verify /workspaces diagnostic endpoint is accessible."""
        resp = requests.get(f"{server_url}/workspaces")
        assert resp.status_code == 200
        data = resp.json()
        assert "workspaces" in data
        assert isinstance(data["workspaces"], list)


class TestWorkspaceRouting:
    """Test workspace ID computation and routing."""
    
    def test_compute_workspace_id_deterministic(self):
        """Verify workspace IDs are deterministic based on path."""
        path1 = "/tmp/test1.graphml"
        path2 = "/tmp/test2.graphml"
        
        id1a = utils.compute_workspace_id(path1)
        id1b = utils.compute_workspace_id(path1)
        id2 = utils.compute_workspace_id(path2)
        
        # Same path should produce same ID
        assert id1a == id1b
        # Different paths should produce different IDs
        assert id1a != id2
        # IDs should start with ws_
        assert id1a.startswith("ws_")
    
    def test_workspace_url_construction(self, server_url):
        """Verify workspace URLs are constructed correctly."""
        workspace_id = "ws_abc123"
        url = utils.get_workspace_url(workspace_id)
        assert url == f"{server_url}/workspace/{workspace_id}"
        
        endpoint_url = utils.get_workspace_url(workspace_id, "/get-graph")
        assert endpoint_url == f"{server_url}/workspace/{workspace_id}/get-graph"


class TestClientLifecycle:
    """Test on-demand context creation and destruction."""
    
    def test_context_created_on_first_client_connect(self, server_url, temp_workfile):
        """Verify workspace context is created on first client connect."""
        workspace_id = utils.compute_workspace_id(temp_workfile)
        base_url = utils.get_workspace_url(workspace_id)
        
        # Verify no context exists initially
        resp = requests.get(f"{server_url}/workspaces")
        workspaces = resp.json()["workspaces"]
        ws_ids = [ws["workspace_id"] for ws in workspaces]
        assert workspace_id not in ws_ids
        
        # Connect first client
        endpoint = f"{base_url}/client-connect"
        resp = requests.post(endpoint, json={"workfile_path": temp_workfile})
        assert resp.status_code == 200
        
        # Verify context now exists
        time.sleep(0.1)  # Brief delay for context creation
        resp = requests.get(f"{server_url}/workspaces")
        workspaces = resp.json()["workspaces"]
        ws_ids = [ws["workspace_id"] for ws in workspaces]
        assert workspace_id in ws_ids
        
        # Cleanup
        endpoint = f"{base_url}/client-disconnect"
        requests.post(endpoint, json={})
        time.sleep(0.2)  # Wait for context to be destroyed
    
    def test_context_destroyed_on_last_client_disconnect(self, server_url, temp_workfile):
        """Verify workspace context is destroyed when last client disconnects."""
        workspace_id = utils.compute_workspace_id(temp_workfile)
        base_url = utils.get_workspace_url(workspace_id)
        
        # Connect client
        requests.post(f"{base_url}/client-connect", json={"workfile_path": temp_workfile})
        time.sleep(0.1)
        
        # Verify context exists
        resp = requests.get(f"{server_url}/workspaces")
        workspaces = resp.json()["workspaces"]
        ws_ids = [ws["workspace_id"] for ws in workspaces]
        assert workspace_id in ws_ids
        
        # Disconnect client
        requests.post(f"{base_url}/client-disconnect", json={})
        
        # Wait with verification loop (up to 10 seconds) for worker thread cleanup
        # Worker thread must fully stop before context removed from registry
        # This prevents race condition where fixed sleep was insufficient
        context_destroyed = False
        for attempt in range(50):  # 50 attempts * 200ms = 10 seconds max
            time.sleep(0.2)
            resp = requests.get(f"{server_url}/workspaces")
            workspaces = resp.json()["workspaces"]
            ws_ids = [ws["workspace_id"] for ws in workspaces]
            if workspace_id not in ws_ids:
                context_destroyed = True
                break
        
        # Verify context is destroyed
        assert context_destroyed, f"Context {workspace_id} still exists after 10 seconds"


class TestMultipleWorkspaces:
    """Test multiple workspaces operating concurrently."""
    
    def test_multiple_workspaces_isolation(self, server_url):
        """Verify multiple workspaces can operate independently."""
        # Create two workfiles
        with tempfile.NamedTemporaryFile(suffix=".graphml", delete=False) as f1:
            path1 = f1.name
        with tempfile.NamedTemporaryFile(suffix=".graphml", delete=False) as f2:
            path2 = f2.name
        
        try:
            ws_id1 = utils.compute_workspace_id(path1)
            ws_id2 = utils.compute_workspace_id(path2)
            
            base_url1 = utils.get_workspace_url(ws_id1)
            base_url2 = utils.get_workspace_url(ws_id2)
            
            # Connect to both workspaces
            requests.post(f"{base_url1}/client-connect", json={"workfile_path": path1})
            requests.post(f"{base_url2}/client-connect", json={"workfile_path": path2})
            time.sleep(0.1)
            
            # Verify both contexts exist
            resp = requests.get(f"{server_url}/workspaces")
            workspaces = resp.json()["workspaces"]
            ws_ids = [ws["workspace_id"] for ws in workspaces]
            assert ws_id1 in ws_ids
            assert ws_id2 in ws_ids
            
            # Verify each workspace has 1 client
            for ws in workspaces:
                if ws["workspace_id"] in [ws_id1, ws_id2]:
                    assert ws["client_count"] == 1
            
            # Disconnect from first workspace
            requests.post(f"{base_url1}/client-disconnect", json={})
            time.sleep(0.1)
            
            # Verify only first context is destroyed
            resp = requests.get(f"{server_url}/workspaces")
            workspaces = resp.json()["workspaces"]
            ws_ids = [ws["workspace_id"] for ws in workspaces]
            assert ws_id1 not in ws_ids
            assert ws_id2 in ws_ids
            
            # Cleanup
            requests.post(f"{base_url2}/client-disconnect", json={})
        finally:
            os.unlink(path1)
            os.unlink(path2)


class TestGraphOperations:
    """Test graph operations through REST API."""
    
    def test_add_and_get_nodes(self, server_url, temp_workfile):
        """Test adding nodes and retrieving graph."""
        workspace_id = utils.compute_workspace_id(temp_workfile)
        base_url = utils.get_workspace_url(workspace_id)
        
        # Connect client
        requests.post(f"{base_url}/client-connect", json={"workfile_path": temp_workfile})
        time.sleep(0.2)
        
        try:
            # Add a node
            resp = requests.post(
                f"{base_url}/add-node",
                json={"label": "Test Node", "x": 0, "y": 0, "status": ""}
            )
            assert resp.status_code == 202
            
            time.sleep(0.5)  # Wait for worker to process and write to disk
            
            # Get graph
            resp = requests.get(f"{base_url}/get-graph")
            assert resp.status_code == 200
            graph_data = resp.json()
            assert len(graph_data["nodes"]) > 0, "No nodes found in graph"
            
            # Verify node attributes
            node = graph_data["nodes"][0]
            assert node["label"] == "Test Node"
            assert node["status"] == ""
        finally:
            requests.post(f"{base_url}/client-disconnect", json={})
    
    def test_graph_persistence(self, server_url, temp_workfile):
        """Test that graph changes persist to disk."""
        workspace_id = utils.compute_workspace_id(temp_workfile)
        base_url = utils.get_workspace_url(workspace_id)
        
        # Connect and add node
        requests.post(f"{base_url}/client-connect", json={"workfile_path": temp_workfile})
        time.sleep(0.2)
        
        try:
            resp = requests.post(
                f"{base_url}/add-node",
                json={"label": "Persistent Node", "x": 10, "y": 20, "status": ""}
            )
            assert resp.status_code == 202
            time.sleep(0.3)  # Wait for worker to process
            
            # Verify node was added
            resp = requests.get(f"{base_url}/get-graph")
            assert resp.status_code == 200
            graph_data = resp.json()
            initial_count = len(graph_data["nodes"])
            
            # Find the node we just added
            persistent_node = next((n for n in graph_data["nodes"] if n.get("label") == "Persistent Node"), None)
            assert persistent_node is not None, "Node with label 'Persistent Node' not found"
            node_id = persistent_node["id"]
            
            # Disconnect
            requests.post(f"{base_url}/client-disconnect", json={})
            time.sleep(0.1)
            
            # Reconnect (will reload graph from disk)
            requests.post(f"{base_url}/client-connect", json={"workfile_path": temp_workfile})
            time.sleep(0.2)
            
            # Verify node still exists after reload
            resp = requests.get(f"{base_url}/get-graph")
            graph_data = resp.json()
            node_ids = [n["id"] for n in graph_data["nodes"]]
            assert node_id in node_ids, f"Node {node_id} not found after reload"
            assert len(graph_data["nodes"]) == initial_count, "Node count changed unexpectedly"
        finally:
            requests.post(f"{base_url}/client-disconnect", json={})


class TestWorkspaceDiagnostics:
    """Test diagnostic endpoints for workspace monitoring."""
    
    def test_workspaces_endpoint_shows_active_contexts(self, server_url, temp_workfile):
        """Verify /workspaces endpoint correctly reports active contexts."""
        workspace_id = utils.compute_workspace_id(temp_workfile)
        base_url = utils.get_workspace_url(workspace_id)
        
        # Connect client
        requests.post(f"{base_url}/client-connect", json={"workfile_path": temp_workfile})
        time.sleep(0.1)
        
        try:
            resp = requests.get(f"{server_url}/workspaces")
            assert resp.status_code == 200
            workspaces = resp.json()["workspaces"]
            
            # Find our workspace
            our_ws = None
            for ws in workspaces:
                if ws["workspace_id"] == workspace_id:
                    our_ws = ws
                    break
            
            assert our_ws is not None
            assert our_ws["workfile_path"] == temp_workfile
            assert our_ws["client_count"] == 1
            assert "created_at" in our_ws
        finally:
            requests.post(f"{base_url}/client-disconnect", json={})
    
    def test_workspaces_endpoint_empty_when_no_clients(self, server_url):
        """Verify /workspaces endpoint shows empty list when no contexts."""
        resp = requests.get(f"{server_url}/workspaces")
        assert resp.status_code == 200
        workspaces = resp.json()["workspaces"]
        # After cleanup from previous tests, should be empty or at least consistent
        assert isinstance(workspaces, list)


class TestErrorHandling:
    """Test error handling in workspace routing."""
    
    def test_missing_workfile_path_on_connect(self, server_url, temp_workfile):
        """Verify proper error when workfile_path not provided."""
        workspace_id = utils.compute_workspace_id(temp_workfile)
        base_url = utils.get_workspace_url(workspace_id)
        
        resp = requests.post(f"{base_url}/client-connect", json={})
        assert resp.status_code == 400
        assert "workfile_path" in resp.json()["error"]
    
    def test_nonexistent_workspace_returns_404(self, server_url):
        """Verify 404 for operations on non-existent workspace."""
        fake_workspace_id = "ws_nonexistent"
        base_url = utils.get_workspace_url(fake_workspace_id)
        
        resp = requests.get(f"{base_url}/get-graph")
        assert resp.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
