#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
server.py — Start, list, or stop Workforce servers associated with GraphML files.
Each file can have at most one active server, tracked by a JSON registry.
"""

from workforce import edit

from contextlib import closing
from flask import Flask, request, jsonify
from flask_socketio import SocketIO
import argparse
import json
import networkx as nx
import os
import platform
import signal
import socket
import subprocess
import sys
import tempfile


REGISTRY_PATH = os.path.join(tempfile.gettempdir(), "workforce_servers.json")


def load_registry():
    if os.path.exists(REGISTRY_PATH):
        try:
            with open(REGISTRY_PATH, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_registry(registry):
    with open(REGISTRY_PATH, "w") as f:
        json.dump(registry, f, indent=2)


def is_port_in_use(port: int) -> bool:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def clean_registry():
    """Remove registry entries whose ports are no longer active."""
    registry = load_registry()
    updated = {}
    for f, info in registry.items():
        port = info.get("port")
        pid = info.get("pid")
        # keep only if port still active
        if is_port_in_use(port):
            updated[f] = info
    if updated != registry:
        save_registry(updated)
    return updated


def default_workfile():
    """Return 'Workfile' in current directory if it exists, else None."""
    default = os.path.join(os.getcwd(), "Workfile")
    return default if os.path.exists(default) else None


def find_free_port(default_port=5000, max_port=6000):
    for port in range(default_port, max_port):
        if not is_port_in_use(port):
            return port
    raise RuntimeError("No free port found in range.")


def list_servers():
    registry = clean_registry()
    if not registry:
        print("No active Workforce servers.")
        return

    print("Active Workforce servers:")
    for fname, info in registry.items():
        print(f"  {fname} → http://127.0.0.1:{info['port']} (PID {info['pid']})")


def stop_server(filename: str):
    """Stop a server by filename (defaults to 'Workfile' if available)."""
    if not filename:
        print("✗ No file specified and no 'Workfile' found in current directory.")
        return

    abs_filename = os.path.abspath(filename)
    registry = clean_registry()

    if abs_filename not in registry:
        print(f"No active server found for '{filename}'.")
        return

    entry = registry.pop(abs_filename)
    port, pid = entry.get("port"), entry.get("pid")
    save_registry(registry)

    if not pid:
        print(f"⚠ No PID recorded for port {port}, cannot terminate automatically.")
        return

    try:
        if platform.system() == "Windows":
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], check=False)
        else:
            os.kill(pid, signal.SIGKILL)
        print(f"✓ Terminated server process (PID {pid}) on port {port}.")
    except ProcessLookupError:
        print(f"⚠ Process {pid} already terminated.")
    except Exception as e:
        print(f"⚠ Failed to kill process {pid}: {e}")


def start_server(filename, port=None, background=True):
    """Start a Workforce server for the given GraphML file."""
    if not filename:
        print("✗ No file specified and no 'Workfile' found in current directory.")
        sys.exit(1)

    abs_filename = os.path.abspath(filename)

    if not os.path.exists(abs_filename):
        print(f"✗ Error: File '{abs_filename}' does not exist.")
        sys.exit(1)

    registry = clean_registry()

    # Prevent multiple servers for the same file
    if abs_filename in registry:
        entry = registry[abs_filename]
        print(f"✓ Server for '{abs_filename}' is already running at http://127.0.0.1:{entry['port']}")
        return

    port = port or find_free_port()

    # Background mode: spawn subprocess in foreground mode
    if background:
        cmd = [sys.executable, os.path.abspath(__file__), "start", abs_filename, "--foreground"]
        process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        pid = process.pid
        print(f"✓ Server for '{abs_filename}' started in background on port {port} (PID {pid}).")

        # Save immediately (port + pid)
        registry[abs_filename] = {"port": port, "pid": pid}
        save_registry(registry)
        return

    # Foreground mode: actually run Flask app
    app = Flask(__name__)
    socketio = SocketIO(app, cors_allowed_origins="*")

    # Save our own PID
    registry[abs_filename] = {"port": port, "pid": os.getpid()}
    save_registry(registry)

    @app.route("/get-graph")
    def get_graph():
        return jsonify(nx.node_link_data(edit.get_graph(abs_filename)))

    @app.route("/save-graph", methods=["POST"])
    def save_graph():
        edit.save_graph(abs_filename, request.json["graph"])
        return jsonify({"status": "ok"})

    @app.route("/add-node", methods=["POST"])
    def add_node():
        data = request.json
        node_id = edit.add_node(abs_filename, data["label"], data.get("x", 0), data.get("y", 0))
        return jsonify({"node_id": node_id})

    print(f"✓ Serving '{abs_filename}' on port {port}")
    print(f"   → http://127.0.0.1:{port}")

    try:
        socketio.run(app, port=port)
    finally:
        # Clean registry if server exits normally
        registry = load_registry()
        if abs_filename in registry:
            registry.pop(abs_filename)
            save_registry(registry)
        print(f"✗ Server for '{abs_filename}' stopped and registry cleaned.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def add_arguments(parser):
    sub = parser.add_subparsers(dest="command", required=False)

    # start
    start_p = sub.add_parser("start", help="Start or connect to a server for a GraphML file.")
    start_p.add_argument("filename", nargs="?", help="Path to the GraphML file (defaults to 'Workfile' if present).")
    start_p.add_argument("--foreground", "-f", action="store_true",
                         help="Run server in foreground (default is background).")
    start_p.set_defaults(func=lambda args: start_server(
        args.filename or default_workfile(),
        background=not args.foreground
    ))

    # stop
    stop_p = sub.add_parser("stop", help="Stop the server for a GraphML file.")
    stop_p.add_argument("filename", nargs="?", help="Path to the GraphML file (defaults to 'Workfile' if present).")
    stop_p.set_defaults(func=lambda args: stop_server(args.filename or default_workfile()))

    # list
    list_p = sub.add_parser("list", help="List all active servers.")
    list_p.set_defaults(func=lambda args: list_servers())


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Workforce server CLI")
    add_arguments(parser)
    args = parser.parse_args()

    # Case 1: subcommand used
    if hasattr(args, "func"):
        args.func(args)

    # Case 2: no subcommand → start default Workfile
    else:
        wf = default_workfile()
        if not wf:
            print(f"✗ No 'Workfile' found in {os.getcwd()}")
            sys.exit(1)
        start_server(wf)

