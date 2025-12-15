import tempfile
import os
import networkx as nx
import pytest
from workforce.edit import graph

def test_add_and_remove_node():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "graph.graphml")
        node = graph.add_node_to_graph(path, "Test Node")
        G = nx.read_graphml(path)
        assert node["node_id"] in G.nodes
        graph.remove_node_from_graph(path, node["node_id"])
        G = nx.read_graphml(path)
        assert node["node_id"] not in G.nodes

def test_add_and_remove_edge():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "graph.graphml")
        n1 = graph.add_node_to_graph(path, "Node1")["node_id"]
        n2 = graph.add_node_to_graph(path, "Node2")["node_id"]
        edge_data = graph.add_edge_to_graph(path, n1, n2)
        assert edge_data is not None
        graph.remove_edge_from_graph(path, n1, n2)
        G = nx.read_graphml(path)
        assert not G.has_edge(n1, n2)
