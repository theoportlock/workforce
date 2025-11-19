# workforce/server/graph_store.py

from typing import Any
import networkx as nx

from workforce.edit import (
    load_graph,
    save_graph,
    add_node_to_graph,
    remove_node_from_graph,
    add_edge_to_graph,
    remove_edge_from_graph,
    edit_status_in_graph,
)


class GraphStore:
    """
    Wraps graph operations for a single GraphML file path.
    """
    def __init__(self, path: str):
        self.path = path

    def load(self) -> nx.Graph:
        return load_graph(self.path)

    def node_link_data(self) -> dict:
        return nx.node_link_data(self.load())

    def save(self, graph: nx.Graph) -> Any:
        return save_graph(self.path, graph)

    def add_node(self, label: str, x: int = 0, y: int = 0, status: str = ""):
        return add_node_to_graph(self.path, label, x, y, status)

    def remove_node(self, node_id: str):
        return remove_node_from_graph(self.path, node_id)

    def add_edge(self, source: str, target: str):
        return add_edge_to_graph(self.path, source, target)

    def remove_edge(self, source: str, target: str):
        return remove_edge_from_graph(self.path, source, target)

    def edit_status(self, element_type: str, element_id: str, value: str = ""):
        return edit_status_in_graph(self.path, element_type, element_id, value)

