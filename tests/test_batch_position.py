"""Test batch node position updates."""
import os
import tempfile
import pytest
from workforce.edit import graph


def test_batch_position_update():
    """Test that edit_node_positions_in_graph updates multiple nodes."""
    # Use a path that doesn't exist yet - load_graph will create it
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, 'test.graphml')
        
        # Create graph with 3 nodes
        result1 = graph.add_node_to_graph(path, "Node A", 0, 0)
        result2 = graph.add_node_to_graph(path, "Node B", 10, 10)
        result3 = graph.add_node_to_graph(path, "Node C", 20, 20)
        
        node_a = result1["node_id"]
        node_b = result2["node_id"]
        node_c = result3["node_id"]
        
        # Batch update positions
        positions = [
            {"node_id": node_a, "x": 100, "y": 200},
            {"node_id": node_b, "x": 150, "y": 250},
            {"node_id": node_c, "x": 200, "y": 300},
        ]
        
        result = graph.edit_node_positions_in_graph(path, positions)
        
        assert result["status"] == "updated"
        assert result["count"] == 3
        assert "missing_nodes" not in result
        
        # Verify positions were updated
        G = graph.load_graph(path)
        assert G.nodes[node_a]["x"] == "100"
        assert G.nodes[node_a]["y"] == "200"
        assert G.nodes[node_b]["x"] == "150"
        assert G.nodes[node_b]["y"] == "250"
        assert G.nodes[node_c]["x"] == "200"
        assert G.nodes[node_c]["y"] == "300"


def test_batch_position_update_with_missing():
    """Test batch update handles missing nodes gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, 'test.graphml')
        
        # Create graph with 2 nodes
        result1 = graph.add_node_to_graph(path, "Node A", 0, 0)
        result2 = graph.add_node_to_graph(path, "Node B", 10, 10)
        
        node_a = result1["node_id"]
        node_b = result2["node_id"]
        
        # Batch update with one missing node
        positions = [
            {"node_id": node_a, "x": 100, "y": 200},
            {"node_id": "nonexistent-id", "x": 150, "y": 250},
            {"node_id": node_b, "x": 200, "y": 300},
        ]
        
        result = graph.edit_node_positions_in_graph(path, positions)
        
        assert result["status"] == "updated"
        assert result["count"] == 2  # Only 2 updated
        assert "missing_nodes" in result
        assert "nonexistent-id" in result["missing_nodes"]
        
        # Verify valid positions were still updated
        G = graph.load_graph(path)
        assert G.nodes[node_a]["x"] == "100"
        assert G.nodes[node_b]["x"] == "200"


def test_batch_position_single_operation():
    """Test batch update works with single file load/save."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, 'test.graphml')
        
        # Create 5 nodes
        nodes = []
        for i in range(5):
            result = graph.add_node_to_graph(path, f"Node {i}", i * 10, i * 10)
            nodes.append(result["node_id"])
        
        # Batch update all 5 nodes
        positions = [
            {"node_id": nid, "x": i * 100, "y": i * 200}
            for i, nid in enumerate(nodes)
        ]
        
        graph.edit_node_positions_in_graph(path, positions)
        
        # Verify all positions are correct
        G = graph.load_graph(path)
        for i, nid in enumerate(nodes):
            assert G.nodes[nid]["x"] == str(i * 100)
            assert G.nodes[nid]["y"] == str(i * 200)


if __name__ == "__main__":
    test_batch_position_update()
    test_batch_position_update_with_missing()
    test_batch_position_single_operation()
    print("✓ All tests passed")
