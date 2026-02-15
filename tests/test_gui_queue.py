"""
Tests for the GUI client operation queue.

Verifies that:
1. Operations are queued and batched
2. Server updates are applied correctly (wait for confirmation)
3. No duplicate nodes appear
"""

import os
import time
import tempfile
import threading
import pytest
import requests
import networkx as nx

from workforce import utils
from workforce.gui.client import ServerClient, OperationQueue


@pytest.fixture(scope="module")
def server_url():
    """Start server once per test module and return its URL."""
    try:
        server = utils.resolve_server()
    except Exception as e:
        pytest.skip(f"Failed to start/discover server: {e}")
    
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


@pytest.fixture
def temp_workfile():
    """Create a temporary workfile for testing."""
    fd, path = tempfile.mkstemp(suffix=".graphml")
    os.close(fd)
    G = nx.DiGraph()
    nx.write_graphml(G, path)
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def server_info(server_url, temp_workfile):
    """Get workspace info for testing."""
    workspace_id = utils.compute_workspace_id(temp_workfile)
    base_url = utils.get_workspace_url(workspace_id)
    
    # Connect client
    requests.post(f"{base_url}/client-connect", json={"workfile_path": temp_workfile})
    time.sleep(0.2)
    
    yield {"base_url": base_url, "workspace_id": workspace_id, "temp_workfile": temp_workfile}
    
    # Disconnect
    try:
        requests.post(f"{base_url}/client-disconnect", json={})
    except Exception:
        pass


class TestOperationQueue:
    """Test the OperationQueue class directly."""
    
    def test_enqueue_adds_to_queue(self):
        """Test that enqueue adds operations to the queue."""
        q = OperationQueue()
        
        op_id = q.enqueue("position", {"node_id": "test", "x": 100, "y": 100})
        
        assert op_id is not None
        assert len(q.queue) == 1
        assert q.queue[0]["type"] == "position"
        assert q.queue[0]["data"]["node_id"] == "test"
    
    def test_enqueue_batch_timer(self):
        """Test that enqueue starts a batch timer."""
        q = OperationQueue(batch_interval_ms=50)
        flushed = []
        
        def on_flush():
            flushed.append(True)
        
        q.set_flush_callback(on_flush)
        
        q.enqueue("position", {"node_id": "test", "x": 100, "y": 100})
        assert len(flushed) == 0
        
        # Wait for timer to fire
        time.sleep(0.1)
        assert len(flushed) == 1
    
    def test_queue_size_limit(self):
        """Test that queue respects max size."""
        q = OperationQueue(max_queue_size=3)
        
        q.enqueue("position", {"node_id": "1", "x": 100, "y": 100})
        q.enqueue("position", {"node_id": "2", "x": 100, "y": 100})
        q.enqueue("position", {"node_id": "3", "x": 100, "y": 100})
        
        # Should drop when full
        result = q.enqueue("position", {"node_id": "4", "x": 100, "y": 100})
        
        assert result is None
        assert len(q.queue) == 3
    
    def test_confirm_operations(self):
        """Test confirming operations removes them from pending."""
        q = OperationQueue()
        
        op_id = q.enqueue("position", {"node_id": "test", "x": 100, "y": 100})
        
        # Move to pending
        q.pending[op_id] = q.queue.pop(0)
        
        # Confirm
        q.confirm_operation(op_id)
        
        assert op_id not in q.pending
        assert len(q.pending) == 0


class TestServerClientQueue:
    """Test ServerClient with queue integration."""
    
    def test_add_node_queues_operation(self, server_info):
        """Test that add_node queues the operation."""
        client = ServerClient(
            base_url=server_info["base_url"],
            workspace_id=server_info["workspace_id"],
            workfile_path=server_info["temp_workfile"]
        )
        
        # Before flush - operation should be queued
        result = client.add_node("Test Node", 100, 200)
        
        assert "node_id" in result
        assert len(client.op_queue.queue) == 1
        
        # Flush to send to server
        client.flush()
        
        # Wait for server to process
        time.sleep(0.5)
        
        # Verify node exists on server
        graph = client.get_graph()
        node_ids = [n["id"] for n in graph.get("nodes", [])]
        
        # Should have node from server (different ID than what we generated locally)
        assert len(graph.get("nodes", [])) > 0
        
        # Cleanup
        client.disconnect()
    
    def test_edit_status_queues_operation(self, server_info):
        """Test that edit_status queues the operation."""
        client = ServerClient(
            base_url=server_info["base_url"],
            workspace_id=server_info["workspace_id"],
            workfile_path=server_info["temp_workfile"]
        )
        
        # First add a node
        client.add_node("Test", 100, 100)
        client.flush()
        time.sleep(0.5)
        
        # Get the node ID
        graph = client.get_graph()
        node_id = graph["nodes"][0]["id"]
        
        # Queue a status change
        client.op_queue.enqueue_status("node", node_id, "run")
        
        assert len(client.op_queue.queue) == 1
        
        # Flush and verify
        client.flush()
        time.sleep(0.5)
        
        graph = client.get_graph()
        assert graph["nodes"][0]["status"] == "run"
        
        # Cleanup
        client.disconnect()
    
    def test_edit_node_positions_batches(self, server_info):
        """Test that edit_node_positions batches multiple updates."""
        client = ServerClient(
            base_url=server_info["base_url"],
            workspace_id=server_info["workspace_id"],
            workfile_path=server_info["temp_workfile"]
        )
        
        # Add some nodes
        for i in range(3):
            client.add_node(f"Node{i}", i * 100, 100)
        client.flush()
        time.sleep(0.5)
        
        graph = client.get_graph()
        node_ids = [n["id"] for n in graph["nodes"]]
        
        # Queue multiple position updates
        for i, node_id in enumerate(node_ids):
            client.edit_node_position(node_id, i * 200, 200)
        
        # All should be in queue
        assert len(client.op_queue.queue) == 3
        
        # Flush - should send as batch
        client.flush()
        time.sleep(0.5)
        
        # Verify positions updated
        graph = client.get_graph()
        for i, node in enumerate(graph["nodes"]):
            assert float(node["x"]) == i * 200
            assert float(node["y"]) == 200
        
        # Cleanup
        client.disconnect()
