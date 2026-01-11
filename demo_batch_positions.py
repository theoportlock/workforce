#!/usr/bin/env python3
"""
Demo script showing the performance improvement of batch node position updates.

This script compares:
1. Individual position updates (old approach)
2. Batch position updates (new approach)
"""
import time
import tempfile
import os
from workforce.edit import graph


def demo_individual_updates(path, nodes, positions):
    """Old approach: Update each node individually."""
    start = time.time()
    for pos in positions:
        graph.edit_node_position_in_graph(path, pos["node_id"], pos["x"], pos["y"])
    elapsed = time.time() - start
    return elapsed


def demo_batch_update(path, positions):
    """New approach: Update all nodes in one operation."""
    start = time.time()
    graph.edit_node_positions_in_graph(path, positions)
    elapsed = time.time() - start
    return elapsed


def main():
    print("🚀 Batch Node Position Update Demo\n")
    print("=" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Test with different node counts
        for node_count in [5, 10, 20]:
            path = os.path.join(tmpdir, f'test_{node_count}.graphml')
            
            # Create nodes
            print(f"\n📊 Testing with {node_count} nodes...")
            nodes = []
            for i in range(node_count):
                result = graph.add_node_to_graph(path, f"Node {i}", i * 10, i * 10)
                nodes.append(result["node_id"])
            
            # Prepare position updates
            positions = [
                {"node_id": nid, "x": i * 100, "y": i * 200}
                for i, nid in enumerate(nodes)
            ]
            
            # Test individual updates
            individual_time = demo_individual_updates(path, nodes, positions)
            print(f"   Individual updates: {individual_time:.4f}s ({node_count} operations)")
            
            # Reset positions
            for i, nid in enumerate(nodes):
                graph.edit_node_position_in_graph(path, nid, i * 10, i * 10)
            
            # Test batch update
            batch_time = demo_batch_update(path, positions)
            print(f"   Batch update:       {batch_time:.4f}s (1 operation)")
            
            # Calculate improvement
            speedup = individual_time / batch_time if batch_time > 0 else float('inf')
            print(f"   ⚡ Speedup:          {speedup:.1f}x faster")
    
    print("\n" + "=" * 60)
    print("✅ Demo complete!\n")
    print("Summary:")
    print("  • Old approach: N separate HTTP requests + N file writes")
    print("  • New approach: 1 HTTP request + 1 file write")
    print("  • GUI drag-and-drop of multiple nodes is now much faster!")


if __name__ == "__main__":
    main()
