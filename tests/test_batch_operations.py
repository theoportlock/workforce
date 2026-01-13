import pytest
import tempfile
import os
from workforce.edit import graph as edit


def test_batch_status_updates():
    """Test batch status update for multiple nodes and edges."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, 'test.graphml')
        
        # Create graph with 3 nodes and 2 edges
        node1_result = edit.add_node_to_graph(path, "node1", 0, 0, "")
        node2_result = edit.add_node_to_graph(path, "node2", 100, 0, "")
        node3_result = edit.add_node_to_graph(path, "node3", 200, 0, "")
        
        node1_id = node1_result["node_id"]
        node2_id = node2_result["node_id"]
        node3_id = node3_result["node_id"]
        
        edge1_result = edit.add_edge_to_graph(path, node1_id, node2_id)
        edge2_result = edit.add_edge_to_graph(path, node2_id, node3_id)
        
        edge1_id = edge1_result["edge_id"]
        edge2_id = edge2_result["edge_id"]
        
        # Batch update all statuses
        updates = [
            {"element_type": "node", "element_id": node1_id, "value": "ran"},
            {"element_type": "node", "element_id": node2_id, "value": "running"},
            {"element_type": "node", "element_id": node3_id, "value": ""},
            {"element_type": "edge", "element_id": edge1_id, "value": "to_run"},
            {"element_type": "edge", "element_id": edge2_id, "value": ""},
        ]
        
        result = edit.edit_statuses_in_graph(path, updates)
        
        assert result["status"] == "updated"
        assert result["count"] == 5
        
        # Verify statuses were updated
        G = edit.load_graph(path)
        assert G.nodes[node1_id]["status"] == "ran"
        assert G.nodes[node2_id]["status"] == "running"
        assert G.nodes[node3_id]["status"] == ""
        
        # Find edges and check statuses
        edge1_data = None
        edge2_data = None
        for u, v, data in G.edges(data=True):
            if str(data.get("id")) == edge1_id:
                edge1_data = data
            if str(data.get("id")) == edge2_id:
                edge2_data = data
        
        assert edge1_data is not None
        assert edge2_data is not None
        assert edge1_data["status"] == "to_run"
        assert edge2_data["status"] == ""


def test_batch_status_fail_fast():
    """Test that batch status update fails fast if any element is missing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, 'test.graphml')
        
        # Create graph with 2 nodes
        node1_result = edit.add_node_to_graph(path, "node1", 0, 0, "")
        node2_result = edit.add_node_to_graph(path, "node2", 100, 0, "")
        
        node1_id = node1_result["node_id"]
        node2_id = node2_result["node_id"]
        
        # Try to update 3 nodes (one doesn't exist)
        updates = [
            {"element_type": "node", "element_id": node1_id, "value": "ran"},
            {"element_type": "node", "element_id": "nonexistent", "value": "running"},
            {"element_type": "node", "element_id": node2_id, "value": "ran"},
        ]
        
        result = edit.edit_statuses_in_graph(path, updates)
        
        assert "error" in result
        assert "nonexistent" in result["error"]
        
        # Verify no statuses were updated (fail-fast)
        G = edit.load_graph(path)
        assert G.nodes[node1_id]["status"] == ""
        assert G.nodes[node2_id]["status"] == ""


def test_remove_node_logs():
    """Test batch log removal from multiple nodes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, 'test.graphml')
        
        # Create graph with 3 nodes
        node1_result = edit.add_node_to_graph(path, "node1", 0, 0, "")
        node2_result = edit.add_node_to_graph(path, "node2", 100, 0, "")
        node3_result = edit.add_node_to_graph(path, "node3", 200, 0, "")
        
        node1_id = node1_result["node_id"]
        node2_id = node2_result["node_id"]
        node3_id = node3_result["node_id"]
        
        # Add execution data to all nodes
        edit.save_node_execution_data_in_graph(
            path, node1_id, "echo test1", "test1\n", "", "1234", "0"
        )
        edit.save_node_execution_data_in_graph(
            path, node2_id, "echo test2", "test2\n", "error\n", "1235", "1"
        )
        edit.save_node_log_in_graph(path, node3_id, "old log format")
        
        # Verify logs exist
        G = edit.load_graph(path)
        assert "command" in G.nodes[node1_id]
        assert "stdout" in G.nodes[node1_id]
        assert "command" in G.nodes[node2_id]
        assert "log" in G.nodes[node3_id]
        
        # Batch remove logs
        result = edit.remove_node_logs_in_graph(path, [node1_id, node2_id, node3_id])
        
        assert result["status"] == "cleared"
        assert result["count"] == 3
        
        # Verify all log fields removed
        G = edit.load_graph(path)
        for node_id in [node1_id, node2_id, node3_id]:
            assert "log" not in G.nodes[node_id]
            assert "command" not in G.nodes[node_id]
            assert "stdout" not in G.nodes[node_id]
            assert "stderr" not in G.nodes[node_id]
            assert "pid" not in G.nodes[node_id]
            assert "error_code" not in G.nodes[node_id]
        
        # Verify other attributes preserved
        assert G.nodes[node1_id]["label"] == "node1"
        assert G.nodes[node2_id]["label"] == "node2"
        assert G.nodes[node3_id]["label"] == "node3"


def test_remove_logs_fail_fast():
    """Test that log removal fails fast if any node is missing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, 'test.graphml')
        
        # Create graph with 2 nodes
        node1_result = edit.add_node_to_graph(path, "node1", 0, 0, "")
        node2_result = edit.add_node_to_graph(path, "node2", 100, 0, "")
        
        node1_id = node1_result["node_id"]
        node2_id = node2_result["node_id"]
        
        # Add logs to both nodes
        edit.save_node_log_in_graph(path, node1_id, "log1")
        edit.save_node_log_in_graph(path, node2_id, "log2")
        
        # Try to remove logs from 3 nodes (one doesn't exist)
        result = edit.remove_node_logs_in_graph(path, [node1_id, "nonexistent", node2_id])
        
        assert "error" in result
        assert "nonexistent" in result["error"]
        
        # Verify no logs were removed (fail-fast)
        G = edit.load_graph(path)
        assert "log" in G.nodes[node1_id]
        assert "log" in G.nodes[node2_id]


def test_batch_operations_single_file_io():
    """Test that batch operations use single load/save cycle."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, 'test.graphml')
        
        # Create graph with 50 nodes
        node_ids = []
        for i in range(50):
            result = edit.add_node_to_graph(path, f"node{i}", i * 10, 0, "")
            node_ids.append(result["node_id"])
        
        # Build batch updates for all 50 nodes
        updates = [{"element_type": "node", "element_id": nid, "value": ""} 
                   for nid in node_ids]
        
        # Batch update (should be single file I/O)
        import time
        start = time.time()
        result = edit.edit_statuses_in_graph(path, updates)
        batch_time = time.time() - start
        
        assert result["status"] == "updated"
        assert result["count"] == 50
        
        # Batch operation should be much faster than 50 individual operations
        # (each individual op would be ~10-50ms, batch should be ~10-50ms total)
        assert batch_time < 0.5  # Should complete in under 500ms
        
        print(f"Batch update of 50 nodes completed in {batch_time*1000:.1f}ms")


def test_empty_batch_operations():
    """Test batch operations with empty arrays."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, 'test.graphml')
        
        # Test empty status updates
        result = edit.edit_statuses_in_graph(path, [])
        assert result["status"] == "updated"
        assert result["count"] == 0
        
        # Test empty log removal
        result = edit.remove_node_logs_in_graph(path, [])
        assert result["status"] == "cleared"
        assert result["count"] == 0
