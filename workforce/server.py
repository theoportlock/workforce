#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
server.py — Start, list, or stop Workforce servers associated with GraphML files.
Each file can have at most one active server, tracked by a JSON registry.
Includes client tracking and auto-shutdown when no clients remain.
Also contains GraphML edit endpoints (add/remove node/edge, edit status).
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
from contextlib import closing

import networkx as nx
from flask import Flask, request, jsonify
from flask_socketio import SocketIO

from workforce.utils import (
    load_registry, save_registry, clean_registry,
    is_port_in_use, find_free_port, default_workfile, REGISTRY_PATH
)


# === Graph helpers (previously in edit.py) ===

def load_graph(path: str) -> nx.DiGraph:
    """Load a GraphML file, creating an empty DiGraph if file missing."""
    if not os.path.exists(path):
        G = nx.DiGraph()
        nx.write_graphml(G, path)
        return G
    G = nx.read_graphml(path)
    # Ensure DiGraph semantics
    if not isinstance(G, nx.DiGraph):
        G = nx.DiGraph(G)
    return G


def save_graph(G: nx.DiGraph, path: str):
    nx.write_graphml(G, path)


def add_node_to_graph(path: str, label: str, x: float = 0.0, y: float = 0.0, status: str = "") -> str:
    """Add a node to the graph on disk and return the new node id."""
    G = load_graph(path)
    node_id = str(uuid.uuid4())
    # NetworkX GraphML expects attribute values to be basic types; store as attributes
    G.add_node(node_id, label=label, x=str(x), y=str(y), status=status)
    save_graph(G, path)
    print(f"Added node {node_id} ({label}) to {path}")
    return node_id


def remove_node_from_graph(path: str, node_id: str) -> bool:
    """Remove a node if present. Returns True if removed."""
    G = load_graph(path)
    if node_id in G:
        G.remove_node(node_id)
        save_graph(G, path)
        print(f"Removed node {node_id} from {path}")
        return True
    print(f"Node {node_id} not found in {path}")
    return False


def add_edge_to_graph(path: str, source: str, target: str) -> dict:
    """
    Add an edge between source and target. Returns dict with edge info.
    On success returns {"edge_id": <id>} else raises ValueError.
    """
    G = load_graph(path)
    if source not in G or target not in G:
        raise ValueError("Both source and target nodes must exist.")
    edge_id = str(uuid.uuid4())
    # store an 'id' attribute on the edge so it can be referenced later
    G.add_edge(source, target, id=edge_id)
    save_graph(G, path)
    print(f"Added edge {edge_id} {source} -> {target} in {path}")
    return {"edge_id": edge_id}


def remove_edge_from_graph(path: str, source: str, target: str) -> bool:
    """Remove edge if exists. Returns True if removed."""
    G = load_graph(path)
    if G.has_edge(source, target):
        G.remove_edge(source, target)
        save_graph(G, path)
        print(f"Removed edge {source} -> {target} from {path}")
        return True
    # maybe user passed an edge_id instead of source/target? no assumption here
    print(f"Edge {source} -> {target} not found in {path}")
    return False


def edit_status_in_graph(path: str, element_type: str, element_id: str, value: str) -> bool:
    """
    Edit status attribute for node or edge.
    For nodes: element_id is node id.
    For edges: element_id is the edge 'id' attribute stored on the edge.
    Returns True if changed.
    """
    G = load_graph(path)
    if element_type == "node":
        if element_id not in G:
            print(f"Node {element_id} not found in {path}")
            return False
        G.nodes[element_id]["status"] = value
        save_graph(G, path)
        print(f"Set node {element_id} status = {value} in {path}")
        return True
    elif element_type == "edge":
        found = False
        for u, v, data in G.edges(data=True):
            if str(data.get("id")) == str(element_id):
                data["status"] = value
                found = True
                break
        if not found:
            print(f"Edge with id={element_id} not found in {path}")
            return False
        save_graph(G, path)
        print(f"Set edge {element_id} status = {value} in {path}")
        return True
    else:
        raise ValueError("element_type must be 'node' or 'edge'.")


# === Server Lifecycle ===

def list_servers():
    registry = clean_registry()
    if not registry:
        print("  No active Workforce servers.")
        return

    print("Active Workforce servers:")
    for path, info in registry.items():
        print(f"  • {path}")
        print(f"    → http://127.0.0.1:{info['port']} (PID {info['pid']}) clients={info.get('clients',0)}")


def stop_server(filename: str | None):
    if not filename:
        print("  No file specified and no 'Workfile' found.")
        return

    abs_path = os.path.abspath(filename)
    registry = clean_registry()

    if abs_path not in registry:
        print(f" No active server found for '{filename}'.")
        return

    entry = registry.pop(abs_path)
    save_registry(registry)

    pid = entry.get("pid")
    port = entry.get("port")

    if not pid:
        print(f"  No PID recorded for {filename}, cannot terminate automatically.")
        return

    try:
        if platform.system() == "Windows":
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], check=False)
        else:
            os.kill(pid, signal.SIGTERM)
        print(f" Terminated server (PID {pid}) for '{filename}' on port {port}.")
    except ProcessLookupError:
        print(f" Process {pid} already terminated.")
    except Exception as e:
        print(f" Failed to stop server: {e}")


def start_server(filename: str, port: int | None = None, background: bool = True):
    if not filename:
        print("  No file specified and no 'Workfile' found.")
        sys.exit(1)

    abs_path = os.path.abspath(filename)
    if not os.path.exists(abs_path):
        print(f" File '{abs_path}' does not exist — creating new.")
        G = nx.DiGraph()
        nx.write_graphml(G, abs_path)

    registry = clean_registry()

    if abs_path in registry:
        entry = registry[abs_path]
        print(f" Server already running for '{abs_path}' at http://127.0.0.1:{entry['port']}")
        return

    port = port or find_free_port()

    if background:
        cmd = [sys.executable, os.path.abspath(__file__), "start",
               abs_path, "--foreground", "--port", str(port)]
        process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        pid = process.pid
        registry[abs_path] = {"port": port, "pid": pid, "clients": 0}
        save_registry(registry)
        print(f" Server for '{abs_path}' started in background on port {port} (PID {pid}).")
        return

    # === Foreground Mode ===
    app = Flask(__name__)
    socketio = SocketIO(app, cors_allowed_origins="*")

    registry[abs_path] = {"port": port, "pid": os.getpid(), "clients": 0}
    save_registry(registry)

    client_count = {"count": 0}
    shutting_down = {"flag": False}

    def save_clients():
        reg = load_registry()
        if abs_path in reg:
            reg[abs_path]["clients"] = client_count["count"]
            save_registry(reg)

    def schedule_shutdown():
        """Wait a few seconds; if still no clients, shut down."""
        def _shutdown_task():
            time.sleep(5)
            if client_count["count"] == 0 and not shutting_down["flag"]:
                shutting_down["flag"] = True
                print(f"No clients remain for '{abs_path}'. Shutting down.")
                os.kill(os.getpid(), signal.SIGINT)
        threading.Thread(target=_shutdown_task, daemon=True).start()

    # --- Client connection endpoints ---
    @app.route("/client-connect", methods=["POST"])
    def client_connect():
        client_count["count"] += 1
        save_clients()
        return jsonify({"clients": client_count["count"]})

    @app.route("/client-disconnect", methods=["POST"])
    def client_disconnect():
        if client_count["count"] > 0:
            client_count["count"] -= 1
        save_clients()
        if client_count["count"] == 0:
            schedule_shutdown()
        return jsonify({"clients": client_count["count"]})

    # --- Graph operations ---

    @app.route("/get-graph", methods=["GET"])
    def get_graph():
        if not os.path.exists(abs_path):
            G = nx.DiGraph()
            nx.write_graphml(G, abs_path)
        G = nx.read_graphml(abs_path)
        return jsonify(nx.node_link_data(G))

    @app.route("/add-node", methods=["POST"])
    def add_node():
        try:
            data = request.get_json(force=True)
            label = data.get("label")
            x = data.get("x", 0)
            y = data.get("y", 0)
            status = data.get("status", "")

            if not label:
                return jsonify({"error": "label missing"}), 400

            node_id = add_node_to_graph(abs_path, label, x, y, status)
            return jsonify({"node_id": node_id}), 200

        except Exception as e:
            print("SERVER ERROR in add-node:", repr(e))
            return jsonify({"error": str(e)}), 500

    @app.route("/remove-node", methods=["POST"])
    def remove_node():
        try:
            data = request.get_json(force=True)
            node_id = data.get("node_id")
            if not node_id:
                return jsonify({"error": "node_id missing"}), 400
            removed = remove_node_from_graph(abs_path, node_id)
            if removed:
                return jsonify({"status": "removed"}), 200
            else:
                return jsonify({"error": "Node not found"}), 404
        except Exception as e:
            print("SERVER ERROR in remove-node:", repr(e))
            return jsonify({"error": str(e)}), 500

    @app.route("/add-edge", methods=["POST"])
    def add_edge():
        try:
            data = request.get_json(force=True)
            source = data.get("source")
            target = data.get("target")
            if not source or not target:
                return jsonify({"error": "source and target required"}), 400
            try:
                info = add_edge_to_graph(abs_path, source, target)
                return jsonify({"edge_id": info["edge_id"]}), 200
            except ValueError as ve:
                return jsonify({"error": str(ve)}), 400
        except Exception as e:
            print("SERVER ERROR in add-edge:", repr(e))
            return jsonify({"error": str(e)}), 500

    @app.route("/remove-edge", methods=["POST"])
    def remove_edge():
        try:
            data = request.get_json(force=True)
            source = data.get("source")
            target = data.get("target")
            if not source or not target:
                return jsonify({"error": "source and target required"}), 400
            removed = remove_edge_from_graph(abs_path, source, target)
            if removed:
                return jsonify({"status": "removed"}), 200
            else:
                return jsonify({"error": "Edge not found"}), 404
        except Exception as e:
            print("SERVER ERROR in remove-edge:", repr(e))
            return jsonify({"error": str(e)}), 500

    @app.route("/edit-status", methods=["POST"])
    def edit_status():
        try:
            data = request.get_json(force=True)
            element_type = data.get("element_type")  # "node" or "edge"
            element_id = data.get("element_id")
            value = data.get("value", "")
            if element_type not in ("node", "edge"):
                return jsonify({"error": "element_type must be 'node' or 'edge'"}), 400
            if not element_id:
                return jsonify({"error": "element_id required"}), 400
            changed = edit_status_in_graph(abs_path, element_type, element_id, value)
            if changed:
                return jsonify({"status": "updated"}), 200
            else:
                return jsonify({"error": f"{element_type} not found"}), 404
        except Exception as e:
            print("SERVER ERROR in edit-status:", repr(e))
            return jsonify({"error": str(e)}), 500

    @app.route("/update-node", methods=["POST"])
    def update_node():
        try:
            data = request.get_json(force=True)
            node_id = data.get("id")
            if not node_id:
                return jsonify({"error": "id required"}), 400
            label = data.get("label")
            x = data.get("x")
            y = data.get("y")
            status = data.get("status", None)

            G = load_graph(abs_path)
            if node_id not in G:
                return jsonify({"error": "node not found"}), 404

            if label is not None:
                G.nodes[node_id]["label"] = label
            if x is not None:
                G.nodes[node_id]["x"] = str(x)
            if y is not None:
                G.nodes[node_id]["y"] = str(y)
            if status is not None:
                G.nodes[node_id]["status"] = status

            save_graph(G, abs_path)
            return jsonify({"status": "updated"}), 200
        except Exception as e:
            print("SERVER ERROR in update-node:", repr(e))
            return jsonify({"error": str(e)}), 500

    @app.route("/save-graph", methods=["POST"])
    def save_graph_endpoint():
        try:
            # re-read and write to ensure file is persisted (safe no-op if file already up-to-date)
            if not os.path.exists(abs_path):
                G = nx.DiGraph()
                nx.write_graphml(G, abs_path)
            G = nx.read_graphml(abs_path)
            nx.write_graphml(G, abs_path)
            return jsonify({"status": "saved"}), 200
        except Exception as e:
            print("SERVER ERROR in save-graph:", repr(e))
            return jsonify({"error": str(e)}), 500

    print(f"\nServing '{abs_path}' on port {port}")
    print(f"  http://127.0.0.1:{port}\n")

    try:
        socketio.run(app, port=port)
    finally:
        reg = load_registry()
        reg.pop(abs_path, None)
        save_registry(reg)
        print(f"Cleaned registry entry for '{abs_path}'.")


# === CLI Parser ===

def add_arguments(parser):
    sub = parser.add_subparsers(dest="command", required=False)

    start_p = sub.add_parser("start", help="Start or connect to a Workforce server.")
    start_p.add_argument("filename", nargs="?", help="Path to GraphML file.")
    start_p.add_argument("--foreground", "-f", action="store_true", help="Run in foreground.")
    start_p.add_argument("--port", type=int, help="Port to bind.")
    start_p.set_defaults(func=lambda args: start_server(
        args.filename or default_workfile(),
        port=args.port,
        background=not args.foreground
    ))

    stop_p = sub.add_parser("stop", help="Stop a running Workforce server.")
    stop_p.add_argument("filename", nargs="?", help="GraphML file path.")
    stop_p.set_defaults(func=lambda args: stop_server(args.filename or default_workfile()))

    list_p = sub.add_parser("list", help="List active Workforce servers.")
    list_p.set_defaults(func=lambda args: list_servers())


# === Entrypoint ===

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Workforce server management CLI")
    add_arguments(parser)
    args = parser.parse_args()

    if hasattr(args, "func"):
        args.func(args)
    else:
        wf = default_workfile()
        if not wf:
            print(f"No 'Workfile' found in {os.getcwd()}")
            sys.exit(1)
        start_server(wf)

