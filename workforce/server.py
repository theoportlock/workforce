#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import platform
import signal
import subprocess
import sys
import threading
import queue

import networkx as nx
from flask import Flask, request, current_app
from flask_socketio import SocketIO

from workforce import utils
from workforce import run
from workforce import edit

# ============================================================
# Server Lifecycle
# ============================================================

def stop_server(filename: str | None):
    if not filename:
        print("No file specified.")
        return

    abs_path = os.path.abspath(filename)
    registry = utils.clean_registry()

    if abs_path not in registry:
        print(f"No active server for '{filename}'")
        return

    entry = registry.pop(abs_path)
    utils.save_registry(registry)

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
    registry = utils.clean_registry()
    if not registry:
        print("No active Workforce servers.")
        return

    print("Active Workforce servers:")
    for path, info in registry.items():
        print(f"  - {path}")
        print(f"    -> http://127.0.0.1:{info['port']} (PID {info['pid']}) clients={info.get('clients', 0)}")


def start_server(filename: str, port: int | None = None, background: bool = True):
    if not filename:
        sys.exit("No file specified")

    abs_path = os.path.abspath(filename)
    registry = utils.clean_registry()

    if abs_path in registry:
        print(f"Server already running: http://127.0.0.1:{registry[abs_path]['port']}")
        return

    if port is None:
        port = utils.find_free_port()

    # ---------------------------------------------------------
    # BACKGROUND MODE: spawn a new Python process
    # ---------------------------------------------------------
    if background:
        cmd = [
            sys.executable,
            "-m", "workforce",
            "server", "start",
            abs_path,
            "--foreground",
            "--port", str(port)
        ]

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=os.getcwd(),
        )

        registry[abs_path] = {"port": port, "pid": process.pid, "clients": 0}
        utils.save_registry(registry)

        print(f"Server started for '{abs_path}' on port {port}")
        return

    # ---------------------------------------------------------
    # FOREGROUND MODE: actually serve
    # ---------------------------------------------------------
    # Everything below EXACTLY as you currently have it
    # (Flask app, SocketIO, routes, worker thread, etc)

    # ============================================================
    # Foreground Server
    # ============================================================

    app = Flask(__name__)
    # Allow all origins for local dev, or restrict if needed
    socketio = SocketIO(
        app,
        cors_allowed_origins="*",
        async_mode='threading',  # <--- ADD THIS LINE
        ping_interval=30,  # Send a ping every 30 seconds
        ping_timeout=90    # Wait 90 seconds for a pong response before disconnecting
    )
    MODIFICATION_QUEUE = queue.Queue()

    def graph_worker():
        print("Graph worker thread started.")
        last_graph = None
        while True:
            func, args, kwargs = MODIFICATION_QUEUE.get()
            try:
                result = func(*args, **kwargs)
                # Broadcast an updated graph to connected clients in the room named by abs_path
                # FIX 1: Explicit namespace ensures it reaches the connected client
                print(f"[DEBUG] Emitting graph_update for {abs_path}") # Add debug print
                socketio.emit("graph_update", result, namespace='/')

                # If we have a previous graph, check for status transitions to emit node lifecycle events
                if last_graph and isinstance(result, dict) and 'nodes' in result:
                    old_status = {n['id']: n.get('status') for n in last_graph.get('nodes', [])}
                    for node in result.get('nodes', []):
                        nid = node['id']
                        new_stat = node.get('status')
                        old_stat = old_status.get(nid)

                        if new_stat == 'run' and old_stat != 'run':
                            socketio.emit("node_ready", {"node_id": nid}, namespace='/')
                        elif new_stat == 'ran' and old_stat != 'ran':
                            socketio.emit("node_done", {"node_id": nid}, namespace='/')
                last_graph = result
            except Exception as e:
                print(f"[ERROR] Graph worker: {e}")
            finally:
                MODIFICATION_QUEUE.task_done()

    # FIX 2: Use SocketIO's background task spawner instead of standard threading
    # This ensures the thread can talk to the WebSocket loop.
    socketio.start_background_task(target=graph_worker)

    # Update registry with actual PID (os.getpid) since this is the running process
    registry[abs_path] = {"port": port, "pid": os.getpid(), "clients": 0}
    utils.save_registry(registry)

    print(f"Serving '{abs_path}' on port {port}")
    print(f"http://127.0.0.1:{port}\n")

    client_count = {"count": 0}

    def update_registry_clients():
        reg = utils.load_registry()
        if abs_path in reg:
            reg[abs_path]["clients"] = client_count["count"]
            utils.save_registry(reg)

    def enqueue(func, *args, **kwargs):
        """
        Place a modification function in the worker queue and return
        a 202 Accepted JSON response using Flask 3.x JSON provider.
        """
        MODIFICATION_QUEUE.put((func, args, kwargs))
        # Use current_app.json.response to avoid Flask jsonify args/kwargs ambiguity in Flask >= 3.x
        return current_app.json.response({"status": "queued"}), 202

    @socketio.on('connect')
    def on_connect():
        # This handler is for logging. Room logic is removed for simplicity.
        print(f"[SocketIO] Client connected.")

    @socketio.on('disconnect')
    def on_disconnect():
        print(f"[SocketIO] Client disconnected.")

    @app.route("/client-connect", methods=["POST"])
    def client_connect():
        client_count["count"] += 1
        update_registry_clients()
        return current_app.json.response({"clients": client_count["count"]})

    @app.route("/client-disconnect", methods=["POST"])
    def client_disconnect():
        client_count["count"] = max(0, client_count["count"] - 1)
        update_registry_clients()

        if client_count["count"] == 0:
            print("[Server] Last client disconnected. Scheduling shutdown in 1 second.")
            # Shutdown in a separate thread to allow this request to complete
            def shutdown():
                time.sleep(1)
                os.kill(os.getpid(), signal.SIGTERM)
            threading.Thread(target=shutdown, daemon=True).start()

        response = {"clients": client_count["count"], "status": "disconnecting" if client_count["count"] == 0 else "ok"}
        return current_app.json.response(response)


    @app.route("/get-graph")
    def get_graph():
        G = edit.load_graph(abs_path)
        data = nx.node_link_data(G, link="links") # use link instead of edges
        data['graph'] = G.graph
        # Ensure prefix/suffix are present
        data['graph'].setdefault('prefix', '')
        data['graph'].setdefault('suffix', '')
        return current_app.json.response(data)


    @app.route("/add-node", methods=["POST"])
    def add_node():
        data = request.get_json(force=True)
        return enqueue(
            edit.add_node_to_graph,
            abs_path,
            data["label"],
            data.get("x", 0),
            data.get("y", 0),
            data.get("status", "")
        )


    @app.route("/remove-node", methods=["POST"])
    def remove_node():
        data = request.get_json(force=True)
        return enqueue(edit.remove_node_from_graph, abs_path, data["node_id"])


    @app.route("/add-edge", methods=["POST"])
    def add_edge():
        data = request.get_json(force=True)
        return enqueue(edit.add_edge_to_graph, abs_path, data["source"], data["target"])


    @app.route("/remove-edge", methods=["POST"])
    def remove_edge():
        data = request.get_json(force=True)
        return enqueue(edit.remove_edge_from_graph, abs_path, data["source"], data["target"])


    @app.route("/edit-status", methods=["POST"])
    def edit_status():
        data = request.get_json(force=True)
        return enqueue(
            edit.edit_status_in_graph,
            abs_path,
            data["element_type"],
            data["element_id"],
            data.get("value", "")
        )

    @app.route("/edit-node-position", methods=["POST"])
    def edit_node_position():
        data = request.get_json(force=True)
        return enqueue(
            edit.edit_node_position_in_graph,
            abs_path,
            data["node_id"],
            data["x"],
            data["y"]
        )

    @app.route("/edit-prefix-suffix", methods=["POST"])
    def edit_prefix_suffix():
        data = request.get_json(force=True)
        return enqueue(
            edit.edit_prefix_suffix_in_graph,
            abs_path,
            data.get("prefix"),
            data.get("suffix")
        )


    @app.route("/run", methods=["POST"])
    def run_pipeline():
        data = request.get_json(force=True) if request.data else {}
        prefix = data.get("prefix", "")
        suffix = data.get("suffix", "")
        threading.Thread(
            target=lambda: run.run_full_pipeline(f"http://127.0.0.1:{port}/get-graph", prefix, suffix),
            daemon=True
        ).start()
        return current_app.json.response({"status": "started"}), 202

    try:
        socketio.run(app, port=port)
    finally:
        reg = utils.load_registry()
        reg.pop(abs_path, None)
        utils.save_registry(reg)
        print("Clean shutdown; registry updated")


# ============================================================
# CLI Bridge Functions
# ============================================================

def cmd_start(args):
    start_server(args.filename or utils.default_workfile(), port=args.port, background=not args.foreground)

def cmd_stop(args):
    stop_server(args.filename or utils.default_workfile())

def cmd_list(args):
    list_servers()
