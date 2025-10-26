#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
edit.py — GraphML editing CLI for Workforce.
Directly reads and writes GraphML files (atomic control now handled by server).
"""

import os
import uuid
import argparse
import networkx as nx


# === IO Functions ===

def load_graph(filename):
    """Load a GraphML file, creating an empty one if it doesn't exist."""
    if not os.path.exists(filename):
        G = nx.DiGraph()
        nx.write_graphml(G, filename)
    return nx.read_graphml(filename)


def save_graph(G, filename):
    """Save the GraphML file."""
    nx.write_graphml(G, filename)


# === Graph Editing Functions ===

def add_node(filename, label, x=0.0, y=0.0, status=""):
    G = load_graph(filename)
    node_id = str(uuid.uuid4())
    G.add_node(node_id, label=label, x=x, y=y, status=status)
    save_graph(G, filename)
    print(f"🟢 Added node {node_id} ({label}) to {filename}")
    return node_id


def remove_node(filename, node_id):
    G = load_graph(filename)
    if node_id not in G:
        print(f"⚠️ Node {node_id} not found in {filename}")
        return
    G.remove_node(node_id)
    save_graph(G, filename)
    print(f"🗑️ Removed node {node_id} from {filename}")


def add_edge(filename, source, target):
    G = load_graph(filename)
    if source not in G or target not in G:
        print("⚠️ Both source and target nodes must exist.")
        return
    G.add_edge(source, target)
    save_graph(G, filename)
    print(f"🔗 Added edge {source} → {target} in {filename}")


def remove_edge(filename, source, target):
    G = load_graph(filename)
    if G.has_edge(source, target):
        G.remove_edge(source, target)
        save_graph(G, filename)
        print(f"❌ Removed edge {source} → {target} from {filename}")
    else:
        print(f"⚠️ Edge {source} → {target} not found in {filename}")


def edit_status(filename, element_type, element_id, value):
    G = load_graph(filename)

    if element_type == "node":
        if element_id not in G:
            print(f"⚠️ Node {element_id} not found in {filename}")
            return
        G.nodes[element_id]["status"] = value
    elif element_type == "edge":
        found = False
        for u, v, data in G.edges(data=True):
            if data.get("id") == element_id:
                data["status"] = value
                found = True
                break
        if not found:
            print(f"⚠️ Edge with id={element_id} not found in {filename}")
            return

    save_graph(G, filename)
    print(f"🟡 Set {element_type} {element_id} status = {value}")


# === CLI Argument Definitions ===

def add_arguments(subparsers):
    """Attach edit commands to the main CLI."""
    parser = subparsers.add_parser("edit", help="Modify Workfile nodes or edges")
    edit_sub = parser.add_subparsers(dest="action", required=True)

    # Add node
    p_add = edit_sub.add_parser("add-node", help="Add a new node")
    p_add.add_argument("filename")
    p_add.add_argument("--label", required=True)
    p_add.add_argument("--x", type=float, default=0.0)
    p_add.add_argument("--y", type=float, default=0.0)
    p_add.add_argument("--status", default="")
    p_add.set_defaults(func=lambda args: add_node(args.filename, args.label, args.x, args.y, args.status))

    # Remove node
    p_rm = edit_sub.add_parser("remove-node", help="Remove a node")
    p_rm.add_argument("filename")
    p_rm.add_argument("node_id")
    p_rm.set_defaults(func=lambda args: remove_node(args.filename, args.node_id))

    # Add edge
    p_edge = edit_sub.add_parser("add-edge", help="Add edge between two nodes")
    p_edge.add_argument("filename")
    p_edge.add_argument("source")
    p_edge.add_argument("target")
    p_edge.set_defaults(func=lambda args: add_edge(args.filename, args.source, args.target))

    # Remove edge
    p_redge = edit_sub.add_parser("remove-edge", help="Remove edge")
    p_redge.add_argument("filename")
    p_redge.add_argument("source")
    p_redge.add_argument("target")
    p_redge.set_defaults(func=lambda args: remove_edge(args.filename, args.source, args.target))

    # Edit status
    p_status = edit_sub.add_parser("edit-status", help="Edit node or edge status")
    p_status.add_argument("filename")
    p_status.add_argument("element_type", choices=["node", "edge"])
    p_status.add_argument("element_id")
    p_status.add_argument("value")
    p_status.set_defaults(func=lambda args: edit_status(args.filename, args.element_type, args.element_id, args.value))


def main():
    # Ensure server is running and run if not for workfile
    # Call server
    parser = argparse.ArgumentParser(description="Workforce GraphML Editor CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    add_arguments(subparsers)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

