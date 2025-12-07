#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
edit.py — CLI client for remote Workforce server API.
All operations send HTTP requests to the server corresponding to the given Workfile.
"""

import networkx as nx
import os
import tempfile
import logging
import uuid

from workforce.utils import _post

log = logging.getLogger(__name__)

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
    log.info(f"Added node {node_id} to graph: {path}")
    return {"node_id": node_id}

def remove_node_from_graph(path, node_id):
    G = load_graph(path)
    if node_id in G:
        G.remove_node(node_id)
        save_graph(G, path)
        log.info(f"Removed node {node_id} from graph: {path}")
        return {"status": "removed"}
    return {"error": "Node not found"}

def add_edge_to_graph(path, source, target):
    G = load_graph(path)
    if source not in G or target not in G:
        return {"error": "Both source and target must exist"}
    edge_id = str(uuid.uuid4())
    G.add_edge(source, target, id=edge_id)
    save_graph(G, path)    
    log.info(f"Added edge {edge_id} ({source} -> {target}) to graph: {path}")
    return nx.node_link_data(G)

def remove_edge_from_graph(path, source, target):
    G = load_graph(path)
    if G.has_edge(source, target):
        G.remove_edge(source, target)
        save_graph(G, path)
        log.info(f"Removed edge ({source} -> {target}) from graph: {path}")
        return {"status": "removed"}
    return {"error": "Edge not found"}

def edit_status_in_graph(path, element_type, element_id, value):
    log.info(f"Updating status of {element_id} to {value}")
    G = load_graph(path)

    if element_type == "node":
        if element_id in G:
            G.nodes[element_id]["status"] = value
            save_graph(G, path)
            log.info(f"Set node {element_id} status to '{value}' in graph: {path}")
            return {"status": "updated"}
        return {"error": "Node not found"}

    if element_type == "edge":
        for u, v, data in G.edges(data=True):
            if str(data.get("id")) == str(element_id):
                data["status"] = value
                save_graph(G, path)
                log.info(f"Set edge {element_id} status to '{value}' in graph: {path}")
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
    return {"status": "updated"}

def edit_wrapper_in_graph(path, wrapper):
    G = load_graph(path)
    if wrapper is not None:
        G.graph['wrapper'] = wrapper
    save_graph(G, path)
    return {"status": "updated"}

def edit_node_label_in_graph(path, node_id, label):
    G = load_graph(path)
    if node_id not in G:
        return {"error": "Node not found"}
    G.nodes[node_id]["label"] = label
    save_graph(G, path)
    return {"status": "updated"}

def save_node_log_in_graph(path, node_id, log):
    G = load_graph(path)
    if node_id not in G:
        return {"error": "Node not found"}
    G.nodes[node_id]["log"] = log
    save_graph(G, path)
    return {"status": "updated"}


# ============================================================
#  Remote Command Implementations (NOW TAKING port ARGUMENT)
# ============================================================

def cmd_add_node(args, base_url):
    payload = {
        "label": args.label,
        "x": args.x,
        "y": args.y,
        "status": args.status,
    }
    print(f"[CLIENT] POST /add-node {payload}")
    resp = _post(base_url, "/add-node", payload)
    print(resp)


def cmd_remove_node(args, base_url):
    payload = {"node_id": args.node_id}
    print(f"[CLIENT] POST /remove-node {payload}")
    resp = _post(base_url, "/remove-node", payload)
    print(resp)


def cmd_add_edge(args, base_url):
    payload = {"source": args.source, "target": args.target}
    print(f"[CLIENT] POST /add-edge {payload}")
    resp = _post(base_url, "/add-edge", payload)
    print(resp)


def cmd_remove_edge(args, base_url):
    payload = {"source": args.source, "target": args.target}
    print(f"[CLIENT] POST /remove-edge {payload}")
    resp = _post(base_url, "/remove-edge", payload)
    print(resp)


def cmd_edit_status(args, base_url):
    payload = {
        "element_type": args.element_type,
        "element_id": args.element_id,
        "value": args.value,
    }
    print(f"[CLIENT] POST /edit-status {payload}")
    resp = _post(base_url, "/edit-status", payload)
    print(resp)


def cmd_edit_position(args, base_url):
    payload = {"node_id": args.node_id, "x": args.x, "y": args.y}
    print(f"[CLIENT] POST /edit-node-position {payload}")
    resp = _post(base_url, "/edit-node-position", payload)
    print(resp)

def cmd_edit_wrapper(args, base_url):
    payload = {"wrapper": args.wrapper}
    print(f"[CLIENT] POST /edit-wrapper {payload}")
    resp = _post(base_url, "/edit-wrapper", payload)
    print(resp)

def cmd_edit_node_label(args, base_url):
    payload = {"node_id": args.node_id, "label": args.label}
    print(f"[CLIENT] POST /edit-node-label {payload}")
    resp = _post(base_url, "/edit-node-label", payload)
    print(resp)

def cmd_save_node_log(args, base_url):
    payload = {"node_id": args.node_id, "log": args.log}
    print(f"[CLIENT] POST /save-node-log {payload}")
    resp = _post(base_url, "/save-node-log", payload)
    print(resp)
