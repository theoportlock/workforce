#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
server.py — Start, list, or stop Workforce servers associated with GraphML files.
Each file can have at most one active server, tracked by a JSON registry.
"""

from workforce import edit

from contextlib import closing
from flask import Flask
from flask_socketio import SocketIO
import argparse
import atexit
import json
import networkx as nx
import os
import signal
import socket
import sys
import tempfile


REGISTRY_PATH = os.path.join(tempfile.gettempdir(), "workforce_servers.json")

def load_registry():
    """Load the JSON registry of active servers."""
    if os.path.exists(REGISTRY_PATH):
        try:
            with open(REGISTRY_PATH, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_registry(registry):
    """Save the JSON registry."""
    with open(REGISTRY_PATH, "w") as f:
        json.dump(registry, f)


def is_port_in_use(port: int) -> bool:
    """Check if a given port is currently in use on localhost."""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def clean_registry():
    """Remove entries for servers that are no longer active."""
    registry = load_registry()
    updated = {}
    for fname, port in registry.items():
        if is_port_in_use(port):
            updated[fname] = port
    save_registry(updated)
    return updated


class GraphMLAtomic:
    """Atomic read/write context manager for GraphML files."""

    def __init__(self, filename):
        self.filename = filename
        self.modified = False

    def __enter__(self):
        if not os.path.exists(self.filename):
            nx.write_graphml(nx.DiGraph(), self.filename)
        self.G = nx.read_graphml(self.filename)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.modified:
            nx.write_graphml(self.G, self.filename)

    def mark_modified(self):
        self.modified = True


def find_free_port(default_port=5000, max_port=6000):
    """Find the first available TCP port starting from default_port."""
    for port in range(default_port, max_port):
        if not is_port_in_use(port):
            return port
    raise RuntimeError("No free port found in range.")


def start_server(filename, port=None):

    app = Flask(__name__)
    socketio = SocketIO(app, cors_allowed_origins="*")
    port = port or find_free_port()

    registry = load_registry()
    registry[os.path.abspath(filename)] = port
    save_registry(registry)

    @app.route("/graph")
    def get_graph():
        with GraphMLAtomic(filename) as g:
            return nx.node_link_data(g.G)  # jsonify graph

    @app.route("/save-graph", methods=["POST"])
    def save_graph():
        data = request.json
        with GraphMLAtomic(filename) as g:
            g.G = nx.node_link_graph(data["graph"])
            g.mark_modified()
        return jsonify({"status": "ok"})

    @app.route("/add-node", methods=["POST"])
    def add_node_route():
        data = request.json
        node_id = edit.add_node(WORKFILE, data["label"], data.get("x", 0), data.get("y", 0))
        return jsonify({"node_id": node_id})

    print(f"Serving {filename} on port {port}")
    socketio.run(app, port=port)


def list_servers():
    """Print all active servers and their ports."""
    registry = clean_registry()
    if not registry:
        print("No active Workforce servers.")
        return
    print("Active Workforce servers:")
    for fname, port in registry.items():
        print(f"  {fname} → http://127.0.0.1:{port}")


def stop_server(filename: str):
    """Stop a server associated with a given file."""
    abs_filename = os.path.abspath(filename)
    registry = clean_registry()

    if abs_filename not in registry:
        print(f"No active server found for '{filename}'.")
        return

    port = registry[abs_filename]
    print(f"Stopping server for '{filename}' on port {port}.")

    # Attempt to remove it from registry (cannot kill process externally)
    registry.pop(abs_filename, None)
    save_registry(registry)
    print("Registry entry removed. You may need to terminate the process manually if still running.")


def add_arguments(subparser):
    """Register server CLI commands."""
    subparsers = subparser.add_subparsers(dest="command", required=True)

    start_p = subparsers.add_parser("start", help="Start or connect to a server for a GraphML file.")
    start_p.add_argument("filename", help="Path to the GraphML file.")
    start_p.set_defaults(func=lambda args: start_server(args.filename))

    stop_p = subparsers.add_parser("stop", help="Stop the server for a GraphML file.")
    stop_p.add_argument("filename", help="Path to the GraphML file.")
    stop_p.set_defaults(func=lambda args: stop_server(args.filename))

    list_p = subparsers.add_parser("list", help="List all active servers.")
    list_p.set_defaults(func=lambda args: list_servers())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Workforce server CLI")
    add_arguments(parser)
    args = parser.parse_args()

    # If called with just a filename (no subcommand), default to "start"
    if args.command is None and len(sys.argv) > 1:
        args.filename = sys.argv[1]
        start_server(args.filename)
    else:
        args.func(args)

