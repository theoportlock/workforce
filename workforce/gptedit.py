#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
edit.py — Workforce CLI client that auto-starts and gracefully disconnects from the server.
"""

import argparse
import json
import networkx as nx
import os
import requests
import subprocess
import sys
import tempfile
import time

REGISTRY_PATH = os.path.join(tempfile.gettempdir(), "workforce_servers.json")


def get_server_url(filename):
    abs_filename = os.path.abspath(filename)
    if not os.path.exists(REGISTRY_PATH):
        return None
    with open(REGISTRY_PATH, "r") as f:
        registry = json.load(f)
    entry = registry.get(abs_filename)
    if not entry:
        return None
    return f"http://127.0.0.1:{entry['port']}"


def ensure_server_running(filename):
    """Ensure a server is active for this file; start it if needed."""
    url = get_server_url(filename)
    if url:
        try:
            requests.get(f"{url}/graph", timeout=1)
            return url
        except Exception:
            pass

    # Start server
    script = os.path.abspath(os.path.join(os.path.dirname(__file__), "server.py"))
    subprocess.run([sys.executable, script, "start", filename], check=False)
    time.sleep(0.5)
    return get_server_url(filename)


def connect_to_server(url):
    requests.post(f"{url}/client-connect")


def disconnect_from_server(url):
    requests.post(f"{url}/client-disconnect")


# === Edit Operations ===

def add_node(filename, label, x=0.0, y=0.0, status=""):
    url = ensure_server_running(filename)
    connect_to_server(url)
    try:
        r = requests.post(f"{url}/add-node", json={"label": label, "x": x, "y": y, "status": status})
        r.raise_for_status()
        node_id = r.json()["node_id"]
        print(f"✅ Added node {node_id} ({label}) to {filename}")
    finally:
        disconnect_from_server(url)


def remove_node(filename, node_id):
    url = ensure_server_running(filename)
    connect_to_server(url)
    try:
        r = requests.post(f"{url}/remove-node", json={"node_id": node_id})
        print(r.json())
    finally:
        disconnect_from_server(url)


def add_edge(filename, source, target):
    url = ensure_server_running(filename)
    connect_to_server(url)
    try:
        r = requests.post(f"{url}/add-edge", json={"source": source, "target": target})
        print(r.json())
    finally:
        disconnect_from_server(url)


def remove_edge(filename, source, target):
    url = ensure_server_running(filename)
    connect_to_server(url)
    try:
        r = requests.post(f"{url}/remove-edge", json={"source": source, "target": target})
        print(r.json())
    finally:
        disconnect_from_server(url)


def edit_status(filename, element_type, element_id, value):
    url = ensure_server_running(filename)
    connect_to_server(url)
    try:
        r = requests.post(f"{url}/edit-status",
                          json={"element_type": element_type, "element_id": element_id, "value": value})
        print(r.json())
    finally:
        disconnect_from_server(url)


# === CLI ===

def main():
    parser = argparse.ArgumentParser(description="Workforce GraphML Editor CLI (auto-managed server)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add-node", help="Add a new node")
    p_add.add_argument("filename")
    p_add.add_argument("--label", required=True)
    p_add.add_argument("--x", type=float, default=0.0)
    p_add.add_argument("--y", type=float, default=0.0)
    p_add.add_argument("--status", default="")
    p_add.set_defaults(func=lambda a: add_node(a.filename, a.label, a.x, a.y, a.status))

    p_rm = sub.add_parser("remove-node", help="Remove a node")
    p_rm.add_argument("filename")
    p_rm.add_argument("node_id")
    p_rm.set_defaults(func=lambda a: remove_node(a.filename, a.node_id))

    p_edge = sub.add_parser("add-edge", help="Add an edge")
    p_edge.add_argument("filename")
    p_edge.add_argument("source")
    p_edge.add_argument("target")
    p_edge.set_defaults(func=lambda a: add_edge(a.filename, a.source, a.target))

    p_redge = sub.add_parser("remove-edge", help="Remove an edge")
    p_redge.add_argument("filename")
    p_redge.add_argument("source")
    p_redge.add_argument("target")
    p_redge.set_defaults(func=lambda a: remove_edge(a.filename, a.source, a.target))

    p_status = sub.add_parser("edit-status", help="Edit node or edge status")
    p_status.add_argument("filename")
    p_status.add_argument("element_type", choices=["node", "edge"])
    p_status.add_argument("element_id")
    p_status.add_argument("value")
    p_status.set_defaults(func=lambda a: edit_status(a.filename, a.element_type, a.element_id, a.value))

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

