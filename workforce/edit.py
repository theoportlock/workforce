#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
edit.py — CLI client for remote Workforce server API.
All operations send HTTP requests to the server corresponding to the given Workfile.
"""

import networkx as nx
import os
import tempfile
import uuid

from workforce.utils import _post

# ----------------------------------------------------------------------
# Graph-manipulation helpers (leave unchanged)
# ----------------------------------------------------------------------

def load_graph(path: str) -> nx.DiGraph:
    if not os.path.exists(path):
        G = nx.DiGraph()
        nx.write_graphml(G, path)
        return G
    G = nx.read_graphml(path)
    return nx.DiGraph(G)

def save_graph(G: nx.DiGraph, path: str):
    dirpath = os.path.dirname(path)
    with tempfile.NamedTemporaryFile(dir=dirpath, delete=False) as tmp:
        tmppath = tmp.name
    nx.write_graphml(G, tmppath)
    os.replace(tmppath, path)

def add_node_to_graph(path, label, x=0.0, y=0.0, status=""):
    G = load_graph(path)
    node_id = str(uuid.uuid4())
    G.add_node(node_id, label=label, x=str(x), y=str(y), status=status)
    save_graph(G, path)
    print(f"[GRAPH] Add node {node_id}")
    return {"node_id": node_id}

def remove_node_from_graph(path, node_id):
    G = load_graph(path)
    if node_id in G:
        G.remove_node(node_id)
        save_graph(G, path)
        print(f"[GRAPH] Remove node {node_id}")
        return {"status": "removed"}
    return {"error": "Node not found"}

def add_edge_to_graph(path, source, target):
    G = load_graph(path)
    if source not in G or target not in G:
        return {"error": "Both source and target must exist"}
    edge_id = str(uuid.uuid4())
    G.add_edge(source, target, id=edge_id)
    save_graph(G, path)
    print(f"[GRAPH] Add edge {edge_id}")
    return nx.node_link_data(G)

def remove_edge_from_graph(path, source, target):
    G = load_graph(path)
    if G.has_edge(source, target):
        G.remove_edge(source, target)
        save_graph(G, path)
        print(f"[GRAPH] Remove edge {source}->{target}")
        return {"status": "removed"}
    return {"error": "Edge not found"}

def edit_status_in_graph(path, element_type, element_id, value):
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

def edit_node_position_in_graph(path, node_id, x, y):
    G = load_graph(path)
    if node_id not in G:
        return {"error": "Node not found"}
    G.nodes[node_id]["x"] = str(x)
    G.nodes[node_id]["y"] = str(y)
    save_graph(G, path)
    print(f"[GRAPH] Node {node_id} position=({x}, {y})")
    return {"status": "updated"}

def edit_prefix_suffix_in_graph(path, prefix, suffix):
    G = load_graph(path)
    if prefix is not None:
        G.graph['prefix'] = prefix
    if suffix is not None:
        G.graph['suffix'] = suffix
    save_graph(G, path)
    print(f"[GRAPH] Graph prefix='{prefix}', suffix='{suffix}'")
    return nx.node_link_data(G)


# ============================================================
#  Remote Command Implementations (NOW TAKING port ARGUMENT)
# ============================================================

def cmd_add_node(args, port):
    payload = {
        "label": args.label,
        "x": args.x,
        "y": args.y,
        "status": args.status,
    }
    print(f"[CLIENT] POST /add-node {payload}")
    resp = _post(port, "/add-node", payload)
    print(resp)


def cmd_remove_node(args, port):
    payload = {"node_id": args.node_id}
    print(f"[CLIENT] POST /remove-node {payload}")
    resp = _post(port, "/remove-node", payload)
    print(resp)


def cmd_add_edge(args, port):
    payload = {"source": args.source, "target": args.target}
    print(f"[CLIENT] POST /add-edge {payload}")
    resp = _post(port, "/add-edge", payload)
    print(resp)


def cmd_remove_edge(args, port):
    payload = {"source": args.source, "target": args.target}
    print(f"[CLIENT] POST /remove-edge {payload}")
    resp = _post(port, "/remove-edge", payload)
    print(resp)


def cmd_edit_status(args, port):
    payload = {
        "element_type": args.element_type,
        "element_id": args.element_id,
        "value": args.value,
    }
    print(f"[CLIENT] POST /edit-status {payload}")
    resp = _post(port, "/edit-status", payload)
    print(resp)


def cmd_edit_position(args, port):
    payload = {"node_id": args.node_id, "x": args.x, "y": args.y}
    print(f"[CLIENT] POST /edit-node-position {payload}")
    resp = _post(port, "/edit-node-position", payload)
    print(resp)

def cmd_edit_prefix_suffix(args, port):
    payload = {"prefix": args.prefix, "suffix": args.suffix}
    print(f"[CLIENT] POST /edit-prefix-suffix {payload}")
    resp = _post(port, "/edit-prefix-suffix", payload)
    print(resp)
