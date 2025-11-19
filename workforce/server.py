#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import os
import platform
import signal
import subprocess
import sys
import threading
import time
import queue

import networkx as nx
from flask import Flask, request, jsonify
from flask_socketio import SocketIO

from workforce.utils import (
    load_registry, save_registry, clean_registry,
    find_free_port, default_workfile
)

from workforce.run import main as run_full_pipeline
from workforce.edit import (
    load_graph, add_node_to_graph, remove_node_from_graph,
    add_edge_to_graph, remove_edge_from_graph,
    edit_status_in_graph
)

# ============================================================
# Server Lifecycle
# ============================================================

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


def list_servers():
    registry = clean_registry()
    if not registry:
        print("No active Workforce servers.")
        return

    print("Active Workforce servers:")
    for path, info in registry.items():
        print(f"  • {path}")
        print(f"    → http://127.0.0.1:{info['port']} (PID {info['pid']}) clients={info.get('clients', 0)}")


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

    if background:
        # FIXED: Use -m workforce.server to ensure imports work correctly in the child process
        cmd = [sys.executable, "-m", "workforce.server", "start", abs_path, "--foreground", "--port", str(port)]

        # Popen inherits env by default, which is what we want
        process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=os.getcwd())

        registry[abs_path] = {"port": port, "pid": process.pid, "clients": 0}
        save_registry(registry)
        print(f"Server started for '{abs_path}' on port {port}")
        return

    # ============================================================
    # Foreground Server
    # ============================================================

    app = Flask(__name__)
    # Allow all origins for local dev, or restrict if needed
    socketio = SocketIO(app, cors_allowed_origins="*")
    MODIFICATION_QUEUE = queue.Queue()

    def graph_worker():
        print("✓ Graph worker thread started.")
        last_graph = None
        while True:
            func, args, kwargs = MODIFICATION_QUEUE.get()
            try:
                result = func(*args, **kwargs)
                socketio.emit("graph_updated", result, room=abs_path)

                if last_graph and 'nodes' in result:
                    old_status = {n['id']: n.get('status') for n in last_graph['nodes']}
                    for node in result['nodes']:
                        nid = node['id']
                        new_stat = node.get('status')
                        old_stat = old_status.get(nid)

                        if new_stat == 'run' and old_stat != 'run':
                            socketio.emit("node_ready", {"node_id": nid}, room=abs_path)
                        elif new_stat == 'ran' and old_stat != 'ran':
                            socketio.emit("node_done", {"node_id": nid}, room=abs_path)
                last_graph = result
            except Exception as e:
                print(f"[ERROR] Graph worker: {e}")
            finally:
                MODIFICATION_QUEUE.task_done()

    threading.Thread(target=graph_worker, daemon=True).start()

    # Update registry with actual PID (os.getpid) since this is the running process
    registry[abs_path] = {"port": port, "pid": os.getpid(), "clients": 0}
    save_registry(registry)

    print(f"\n≡ƒôí Serving '{abs_path}' on port {port}")
    print(f"Γ₧í∩╕Å  http://127.0.0.1:{port}\n")

    client_count = {"count": 0}

    def update_registry_clients():
        reg = load_registry()
        if abs_path in reg:
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
        return jsonify({"clients": client_count["count"]})

    def enqueue(func, *args, **kwargs):
        MODIFICATION_QUEUE.put((func, args, kwargs))
        return jsonify({"status": "queued"}), 202

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

    @app.route("/run", methods=["POST"])
    def run_pipeline():
        data = request.get_json(force=True) if request.data else {}
        prefix = data.get("prefix", "")
        suffix = data.get("suffix", "")
        threading.Thread(target=lambda: run_full_pipeline(f"http://127.0.0.1:{port}/get-graph", prefix, suffix), daemon=True).start()
        return jsonify({"status": "started"}), 202

    try:
        socketio.run(app, port=port)
    finally:
        reg = load_registry()
        reg.pop(abs_path, None)
        save_registry(reg)
        print("≡ƒöî Clean shutdown; registry updated")


# ============================================================
# CLI Bridge Functions
# ============================================================

def cmd_start(args):
    start_server(args.filename or default_workfile(), port=args.port, background=not args.foreground)

def cmd_stop(args):
    stop_server(args.filename or default_workfile())

def cmd_list(args):
    list_servers()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")

    start_p = sub.add_parser("start")
    start_p.add_argument("filename", nargs="?")
    start_p.add_argument("--foreground", "-f", action="store_true")
    start_p.add_argument("--port", type=int)
    start_p.set_defaults(func=cmd_start)

    stop_p = sub.add_parser("stop")
    stop_p.add_argument("filename", nargs="?")
    stop_p.set_defaults(func=cmd_stop)

    list_p = sub.add_parser("list")
    list_p.set_defaults(func=cmd_list)

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        cmd_start(type("Args", (), {"filename": default_workfile(), "foreground": False, "port": None})())
