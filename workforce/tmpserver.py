#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Workforce server — manages a single GraphML file and communicates with GUI clients via Socket.IO.
"""

from workforce import edit
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
import argparse
import json
import networkx as nx
import os
import sys
import tempfile
from contextlib import closing
import socket
import atexit


REGISTRY_PATH = os.path.join(tempfile.gettempdir(), "workforce_servers.json")


def is_port_in_use(port: int) -> bool:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def find_free_port(default_port=5000, max_port=6000):
    for port in range(default_port, max_port):
        if not is_port_in_use(port):
            return port
    raise RuntimeError("No free port found in range.")


def load_registry():
    if os.path.exists(REGISTRY_PATH):
        with open(REGISTRY_PATH, "r") as f:
            return json.load(f)
    return {}


def save_registry(reg):
    with open(REGISTRY_PATH, "w") as f:
        json.dump(reg, f)


def start_server(filename, port=None):
    filename = os.path.abspath(filename)
    port = port or find_free_port()

    # Load or create graph
    if os.path.exists(filename):
        G = nx.read_graphml(filename)
    else:
        G = nx.DiGraph()
        nx.write_graphml(G, filename)

    app = Flask(__name__)
    socketio = SocketIO(app, cors_allowed_origins="*")

    # Register the server
    registry = load_registry()
    registry[filename] = port
    save_registry(registry)

    @atexit.register
    def unregister():
        reg = load_registry()
        reg.pop(filename, None)
        save_registry(reg)

    @app.route("/save", methods=["POST"])
    def save_graph():
        """Save in-memory graph to file."""
        nx.write_graphml(G, filename)
        return jsonify({"status": "saved"})


    @socketio.on("connect")
    def on_connect():
        print("Client connected")
        emit("graph_data", nx.node_link_data(G))  # send full graph on connect

    @socketio.on("disconnect")
    def on_disconnect():
        print("Client disconnected")

    @socketio.on("add_node")
    def handle_add_node(data):
        """Add a node and broadcast update."""
        node_id = data.get("id")
        label = data.get("label", "")
        pos = {"x": data.get("x", 0), "y": data.get("y", 0)}

        G.add_node(node_id, label=label, **pos)
        socketio.emit("graph_updated", {"type": "add_node", "node": dict(id=node_id, label=label, **pos)})

    @socketio.on("add_edge")
    def handle_add_edge(data):
        """Add an edge and broadcast update."""
        src, tgt = data["source"], data["target"]
        G.add_edge(src, tgt)
        socketio.emit("graph_updated", {"type": "add_edge", "source": src, "target": tgt})

    @socketio.on("update_node")
    def handle_update_node(data):
        """Update node position or label."""
        node_id = data["id"]
        if node_id in G.nodes:
            G.nodes[node_id].update(data)
            socketio.emit("graph_updated", {"type": "update_node", "node": {"id": node_id, **G.nodes[node_id]}})

    @socketio.on("delete_node")
    def handle_delete_node(data):
        """Delete a node."""
        node_id = data["id"]
        if node_id in G.nodes:
            G.remove_node(node_id)
            socketio.emit("graph_updated", {"type": "delete_node", "id": node_id})

    @socketio.on("save_graph")
    def handle_save():
        nx.write_graphml(G, filename)
        print(f"Graph saved: {filename}")
        emit("save_complete", {"status": "ok"})

    print(f"Serving {filename} on port {port}")
    socketio.run(app, port=port)

import subprocess
import time
import socketio
import uuid

# -------------------------------
# CLI/Client interaction utilities
# -------------------------------

def ensure_server_running(filename):
    """Ensure a Workforce server is running for the given file.
    Returns (host, port) tuple.
    """
    filename = os.path.abspath(filename)
    registry = load_registry()

    if filename in registry:
        port = registry[filename]
        print(f"✓ Found existing server for {filename} on port {port}")
    else:
        print(f"⚙️  No server found for {filename}, starting one...")
        port = find_free_port()
        subprocess.Popen(
            ["python3", "-m", "workforce.serve", "start", filename, "--port", str(port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(1.5)
        registry[filename] = port
        save_registry(registry)
        print(f"🚀 Started server for {filename} on port {port}")

    return "127.0.0.1", port


def get_client(filename):
    """Connect to the Socket.IO server for the given file."""
    host, port = ensure_server_running(filename)
    sio = socketio.Client()
    sio.connect(f"http://{host}:{port}")
    return sio


def add_node(filename, label, x=0.0, y=0.0, status="ready"):
    sio = get_client(filename)
    node_id = str(uuid.uuid4())
    sio.emit("add_node", {"id": node_id, "label": label, "x": x, "y": y, "status": status})
    print(f"🧩 Added node {node_id} ({label}) to {filename}")
    sio.disconnect()
    return node_id


def remove_node(filename, node_id):
    sio = get_client(filename)
    sio.emit("delete_node", {"id": node_id})
    print(f"❌ Removed node {node_id} from {filename}")
    sio.disconnect()


def add_edge(filename, source, target):
    sio = get_client(filename)
    sio.emit("add_edge", {"source": source, "target": target})
    print(f"🔗 Added edge {source} → {target} in {filename}")
    sio.disconnect()


def remove_edge(filename, source, target):
    sio = get_client(filename)
    sio.emit("delete_edge", {"source": source, "target": target})
    print(f"🪓 Removed edge {source} → {target} from {filename}")
    sio.disconnect()


def edit_status(filename, element_type, element_id, value):
    sio = get_client(filename)
    sio.emit("edit_status", {"type": element_type, "id": element_id, "value": value})
    print(f"⚙️  Set {element_type} {element_id} status = {value}")
    sio.disconnect()

