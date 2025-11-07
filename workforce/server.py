#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
server.py — Workforce graph server with safe serialized graph modification.

✅ All GraphML writes are routed through a dedicated queue worker
   → Prevents race conditions / corruption
✅ FIFO ordering ensures endpoint execution is deterministic
✅ Non-blocking HTTP responses (202 Accepted on queued tasks)

"""

import argparse
import json
import os
import platform
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import queue
from contextlib import closing

import networkx as nx
from flask import Flask, request, jsonify
from flask_socketio import SocketIO

from workforce.utils import (
    load_registry, save_registry, clean_registry,
    is_port_in_use, find_free_port, default_workfile, REGISTRY_PATH
)


# ============================================================
# Graph Helper Functions
# ============================================================

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
    nx.write_graphml(G, path)


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
    return {"edge_id": edge_id}


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


def update_node_to_graph(path: str, payload: dict) -> dict:
    """Wrapper used by queue worker."""
    G = load_graph(path)
    node_id = payload.get("id")

    if node_id not in G:
        return {"error": "node not found"}

    for key in ("label", "status"):
        if key in payload:
            G.nodes[node_id][key] = payload[key]

    if "x" in payload:
        G.nodes[node_id]["x"] = str(payload["x"])
    if "y" in payload:
        G.nodes[node_id]["y"] = str(payload["y"])

    save_graph(G, path)
    print(f"[GRAPH] update-node {node_id}")
    return {"status": "updated"}


# ============================================================
# Server Lifecycle
# ============================================================

def list_servers():
    registry = clean_registry()
    if not registry:
        print("No active Workforce servers.")
        return

    print("Active Workforce servers:")
    for path, info in registry.items():
        print(f"  • {path}")
        print(f"    → http://127.0.0.1:{info['port']} (PID {info['pid']}) clients={info.get('clients', 0)}")


def stop_server(filename: str | None):
    if not filename:
        print("No file specified.")
        return

    abs_path = os.path.abspath(filename)
    registry = clean_registry()

    if abs_path not in registry:
        print(f"No active server for '{filename}'")
        return

    entry = registry.pop(abs_path)
    save_registry(registry)

    pid = entry.get("pid")
    port = entry.get("port")

    try:
        if platform.system() == "Windows":
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], check=False)
        else:
            os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        print("Process already stopped")

    print(f"Stopped server for '{filename}' (PID {pid}) port {port}")


def start_server(filename: str, port: int | None = None, background: bool = True):
    if not filename:
        sys.exit("No file specified")

    abs_path = os.path.abspath(filename)

    registry = clean_registry()

    if abs_path in registry:
        print(f"Server already running: http://127.0.0.1:{registry[abs_path]['port']}")
        return

    if port is None:
        port = find_free_port()

    # Run new detached process
    if background:
        cmd = [sys.executable, os.path.abspath(__file__), "start", abs_path, "--foreground", "--port", str(port)]
        process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        registry[abs_path] = {"port": port, "pid": process.pid, "clients": 0}
        save_registry(registry)
        print(f"Server started for '{abs_path}' on port {port}")
        return

    # ============================================================
    # Foreground server + Queue Worker
    # ============================================================

    app = Flask(__name__)
    socketio = SocketIO(app, cors_allowed_origins="*")

    MODIFICATION_QUEUE = queue.Queue()

    def graph_worker():
        print("✅ Graph worker thread started.")
        while True:
            func, args, kwargs = MODIFICATION_QUEUE.get()
            try:
                result = func(*args, **kwargs)
                socketio.emit("graph_updated", result, room=abs_path)
            except Exception as e:
                print(f"[ERROR] Graph worker: {e}")
            finally:
                MODIFICATION_QUEUE.task_done()

    threading.Thread(target=graph_worker, daemon=True).start()

    registry[abs_path] = {"port": port, "pid": os.getpid(), "clients": 0}
    save_registry(registry)

    print(f"\n📡 Serving '{abs_path}' on port {port}")
    print(f"➡️  http://127.0.0.1:{port}\n")

    client_count = {"count": 0}

    # ------------------------------------------------------------
    # Client connect/disconnect
    # ------------------------------------------------------------

    def update_registry_clients():
        reg = load_registry()
        reg[abs_path]["clients"] = client_count["count"]
        save_registry(reg)

    @app.route("/client-connect", methods=["POST"])
    def client_connect():
        client_count["count"] += 1
        update_registry_clients()
        return jsonify({"clients": client_count["count"]})

    @app.route("/client-disconnect", methods=["POST"])
    def client_disconnect():
        client_count["count"] = max(0, client_count["count"] - 1)
        update_registry_clients()
        if client_count["count"] == 0:
            threading.Thread(target=lambda: (time.sleep(5), os.kill(os.getpid(), signal.SIGINT)), daemon=True).start()
        return jsonify({"clients": client_count["count"]})


    # ------------------------------------------------------------
    # Graph operations (all queued)
    # ------------------------------------------------------------

    def enqueue(func, *args, **kwargs):
        """Helper to put tasks into queue."""
        MODIFICATION_QUEUE.put((func, args, kwargs))
        return jsonify({"status": "queued"}), 202

    # Get graph
    @app.route("/get-graph", methods=["GET"])
    def get_graph():
        return jsonify(nx.node_link_data(load_graph(abs_path)))

    @app.route("/add-node", methods=["POST"])
    def add_node():
        data = request.get_json(force=True)
        return enqueue(add_node_to_graph, abs_path, data["label"], data.get("x", 0), data.get("y", 0), data.get("status", ""))

    @app.route("/remove-node", methods=["POST"])
    def remove_node():
        data = request.get_json(force=True)
        return enqueue(remove_node_from_graph, abs_path, data["node_id"])

    @app.route("/add-edge", methods=["POST"])
    def add_edge():
        data = request.get_json(force=True)
        return enqueue(add_edge_to_graph, abs_path, data["source"], data["target"])

    @app.route("/remove-edge", methods=["POST"])
    def remove_edge():
        data = request.get_json(force=True)
        return enqueue(remove_edge_from_graph, abs_path, data["source"], data["target"])

    @app.route("/edit-status", methods=["POST"])
    def edit_status():
        data = request.get_json(force=True)
        return enqueue(edit_status_in_graph, abs_path, data["element_type"], data["element_id"], data.get("value", ""))

    @app.route("/update-node", methods=["POST"])
    def update_node():
        data = request.get_json(force=True)
        return enqueue(update_node_to_graph, abs_path, data)


    # ------------------------------------------------------------
    # Start server
    # ------------------------------------------------------------

    try:
        socketio.run(app, port=port)
    finally:
        reg = load_registry()
        reg.pop(abs_path, None)
        save_registry(reg)
        print("🔌 Clean shutdown; registry updated")


# ============================================================
# CLI
# ============================================================

def add_arguments(parser):
    sub = parser.add_subparsers(dest="command", required=False)

    start_p = sub.add_parser("start")
    start_p.add_argument("filename", nargs="?")
    start_p.add_argument("--foreground", "-f", action="store_true")
    start_p.add_argument("--port", type=int)
    start_p.set_defaults(func=lambda args: start_server(
        args.filename or default_workfile(),
        port=args.port,
        background=not args.foreground
    ))

    stop_p = sub.add_parser("stop")
    stop_p.add_argument("filename", nargs="?")
    stop_p.set_defaults(func=lambda args: stop_server(args.filename or default_workfile()))

    list_p = sub.add_parser("list")
    list_p.set_defaults(func=lambda args: list_servers())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Workforce server management CLI")
    add_arguments(parser)
    args = parser.parse_args()

    if hasattr(args, "func"):
        args.func(args)
    else:
        start_server(default_workfile())
