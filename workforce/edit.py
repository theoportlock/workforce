#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
edit.py — Command-line client for Workforce server API.
Performs remote edits via HTTP endpoints exposed by server.py.
"""

import networkx as nx
import os
import pandas as pd
import tempfile
import uuid

def load_graph(path: str) -> nx.DiGraph:
    """Load or create GraphML file."""
    if not os.path.exists(path):
        G = nx.DiGraph()
        nx.write_graphml(G, path)
        return G
    G = nx.read_graphml(path)
    if not isinstance(G, nx.DiGraph):
        G = nx.DiGraph(G)
    return G


def save_graph(G: nx.DiGraph, path: str):
    dirpath = os.path.dirname(path)
    with tempfile.NamedTemporaryFile(dir=dirpath, delete=False) as tmp:
        tmppath = tmp.name
    nx.write_graphml(G, tmppath)
    os.replace(tmppath, path)


def add_node_to_graph(path: str, label: str, x: float = 0.0, y: float = 0.0, status: str = "") -> dict:
    G = load_graph(path)
    node_id = str(uuid.uuid4())
    G.add_node(node_id, label=label, x=str(x), y=str(y), status=status)
    save_graph(G, path)
    print(f"[GRAPH] Add node {node_id}")
    return {"node_id": node_id}


def remove_node_from_graph(path: str, node_id: str) -> dict:
    G = load_graph(path)
    if node_id in G:
        G.remove_node(node_id)
        save_graph(G, path)
        print(f"[GRAPH] Remove node {node_id}")
        return {"status": "removed"}
    return {"error": "Node not found"}


def add_edge_to_graph(path: str, source: str, target: str) -> dict:
    G = load_graph(path)
    if source not in G or target not in G:
        return {"error": "Both source and target must exist"}
    edge_id = str(uuid.uuid4())
    G.add_edge(source, target, id=edge_id)
    save_graph(G, path)
    print(f"[GRAPH] Add edge {edge_id}")
    return nx.node_link_data(G)


def remove_edge_from_graph(path: str, source: str, target: str) -> dict:
    G = load_graph(path)
    if G.has_edge(source, target):
        G.remove_edge(source, target)
        save_graph(G, path)
        print(f"[GRAPH] Remove edge {source}->{target}")
        return {"status": "removed"}
    return {"error": "Edge not found"}


def edit_status_in_graph(path: str, element_type: str, element_id: str, value: str) -> dict:
    G = load_graph(path)

    if element_type == "node":
        if element_id in G:
            G.nodes[element_id]["status"] = value
            save_graph(G, path)
            print(f"[GRAPH] Node {element_id} status={value}")
            return {"status": "updated"}
        return {"error": "Node not found"}

    if element_type == "edge":
        for u, v, data in G.edges(data=True):
            if str(data.get("id")) == str(element_id):
                data["status"] = value
                save_graph(G, path)
                print(f"[GRAPH] Edge {element_id} status={value}")
                return {"status": "updated"}
        return {"error": "Edge not found"}

    return {"error": "element_type must be node or edge"}


def edit_node_position_in_graph(path: str, node_id: str, x: float, y: float) -> dict:
    """Edit the (x, y) position of a node in the GraphML graph."""
    G = load_graph(path)

    if node_id not in G:
        return {"error": "Node not found"}

    # GraphML stores attributes as strings, so convert
    G.nodes[node_id]["x"] = str(x)
    G.nodes[node_id]["y"] = str(y)

    save_graph(G, path)
    print(f"[GRAPH] Node {node_id} position=({x}, {y})")

    return {"status": "updated"}
