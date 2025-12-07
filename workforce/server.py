#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import queue
import platform
import signal
import subprocess
import threading
import queue
import json
import time
import uuid
import sys

import networkx as nx
from flask import Flask, request, current_app
from flask_socketio import SocketIO

import platformdirs
from workforce import utils
from workforce import edit

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("werkzeug").setLevel(logging.WARNING)

log = logging.getLogger(__name__)

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
        log.warning(f"No active server found for '{filename}'")
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
        log.info("Server process %s already stopped.", pid)

    log.info(f"Stopped server for '{filename}' (PID {pid}) on port {port}")


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
        log.info(f"Server for '{abs_path}' already running on port {registry[abs_path]['port']}")
        return

    if port is None:
        port = utils.find_free_port()

    # ---------------------------------------------------------
    # BACKGROUND MODE
    # ---------------------------------------------------------
    if background and sys.platform != "emscripten":
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

        log.info(f"Server started for '{abs_path}' on port {port} with PID {process.pid}")
        return

    # ============================================================
    # FOREGROUND — ACTUAL SERVER
    # ============================================================

    app = Flask(__name__)

    # Create a cache directory for this server instance's requests
    cache_dir = platformdirs.user_cache_dir("workforce")
    server_cache_dir = os.path.join(cache_dir, str(os.getpid()))
    os.makedirs(server_cache_dir, exist_ok=True)
    log.info(f"Caching requests to {server_cache_dir}")
    socketio = SocketIO(
        app,
        cors_allowed_origins="*",
        async_mode="threading",
        ping_interval=30,
        ping_timeout=90,
    )

    MODIFICATION_QUEUE = queue.Queue()

    # ------------------------------------------------------------
    # GRAPH WORKER — simplified, no diffing, always emits lifecycle
    # ------------------------------------------------------------
    def graph_worker():
        log.info("Graph worker thread started.")
        while True:
            func, args, kwargs = MODIFICATION_QUEUE.get()
            try:
                result = func(*args, **kwargs)

                # Broadcast graph update
                log.debug(f"Emitting graph_update for {abs_path}")
                socketio.emit("graph_update", result, namespace="/")

                # Emit lifecycle messages for every node
                for node in result.get("nodes", []):
                    nid = node["id"]
                    stat = node.get("status", "")
                    label = node.get("label", "")

                    if stat == "run":
                        log.debug(f"Emitting node_ready for {nid} with label.")
                        socketio.emit("node_ready", {"node_id": nid, "label": label}, namespace="/")

                    elif stat == "ran":
                        log.debug(f"Emitting node_done for {nid}")
                        socketio.emit("node_done", {"node_id": nid}, namespace="/")

            except Exception as e:
                log.error(f"Graph worker error: {e}", exc_info=True)

            finally:
                MODIFICATION_QUEUE.task_done()

    socketio.start_background_task(target=graph_worker)

    # Update registry with running server info
    registry[abs_path] = {"port": port, "pid": os.getpid(), "clients": 0}
    utils.save_registry(registry)

    log.info(f"Serving '{abs_path}' on http://127.0.0.1:{port}")

    client_state = {"count": 0, "lock": threading.Lock()}

    def update_registry_clients():
        with client_state["lock"]:
            reg = utils.load_registry()
            if abs_path in reg:
                reg[abs_path]["clients"] = client_state["count"]
                utils.save_registry(reg)

    # Helper to enqueue graph modifications
    def enqueue(func, *args, **kwargs):
        # Save request for undo/redo
        try:
            request_id = str(uuid.uuid4())
            request_file = os.path.join(server_cache_dir, f"{request_id}.json")
            # The first arg is always the path, which we don't need to store
            payload = {
                "operation": func.__name__,
                "args": args[1:],
                "kwargs": kwargs,
            }
            with open(request_file, "w") as f:
                json.dump(payload, f)
        except Exception as e:
            log.error(f"Failed to cache request: {e}", exc_info=True)

        MODIFICATION_QUEUE.put((func, args, kwargs))
        return current_app.json.response({"status": "queued"}), 202

    # ------------------------------------------------------------
    # SOCKETIO EVENTS
    # ------------------------------------------------------------
    @socketio.on("connect")
    def on_connect():
        log.info("SocketIO client connected: %s", request.sid)

    @socketio.on("disconnect")
    def on_disconnect():
        log.info("SocketIO client disconnected: %s", request.sid)

    # ------------------------------------------------------------
    # HTTP ROUTES
    # ------------------------------------------------------------

    @app.route("/client-connect", methods=["POST"])
    def client_connect():
        with client_state["lock"]:
            client_state["count"] += 1
            count = client_state["count"]
        update_registry_clients()
        return current_app.json.response({"clients": count})

    @app.route("/client-disconnect", methods=["POST"])
    def client_disconnect():
        with client_state["lock"]:
            client_state["count"] = max(0, client_state["count"] - 1)
            count = client_state["count"]

            if count == 0:
                log.info("Last client disconnected. Scheduling shutdown in 1 second.")

                def shutdown():
                    time.sleep(1)
                    os.kill(os.getpid(), signal.SIGTERM)

                threading.Thread(target=shutdown, daemon=True).start()

        update_registry_clients()
        response = {
            "clients": count,
            "status": "disconnecting" if count == 0 else "ok"
        }
        return current_app.json.response(response)

    @app.route("/get-graph")
    def get_graph():
        G = edit.load_graph(abs_path)
        data = nx.node_link_data(G, link="links")
        data["graph"] = G.graph
        data["graph"].setdefault("prefix", "")
        data["graph"].setdefault("suffix", "")
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

    @app.route("/edit-wrapper", methods=["POST"])
    def edit_wrapper():
        data = request.get_json(force=True)
        return enqueue(
            edit.edit_wrapper_in_graph,
            abs_path,
            data.get("wrapper")
        )

    @app.route("/edit-node-label", methods=["POST"])
    def edit_node_label():
        data = request.get_json(force=True)
        return enqueue(
            edit.edit_node_label_in_graph,
            abs_path,
            data["node_id"],
            data["label"]
        )

    @app.route("/save-node-log", methods=["POST"])
    def save_node_log_api():
        data = request.get_json(force=True)
        return enqueue(
            edit.save_node_log_in_graph,
            abs_path,
            data["node_id"],
            data["log"]
        )

    @app.route("/run", methods=["POST"])
    def run_pipeline():
        data = request.get_json(force=True) if request.data else {}
        start_nodes = data.get("nodes")
        
        # This endpoint now simply kicks off the process by marking nodes to 'run'.
        # The standalone run.py client will listen for 'node_ready' events and execute them.
        
        G = edit.load_graph(abs_path)
        
        nodes_to_start = []
        if start_nodes:
            # If specific nodes are provided, start them.
            nodes_to_start = start_nodes
        else:
            # Otherwise, start all root nodes (nodes with no parents).
            nodes_to_start = [n for n, d in G.in_degree() if d == 0]
            
        if not nodes_to_start:
            return current_app.json.response({"status": "no nodes to start"}), 200
            
        log.info(f"Queuing initial nodes for run: {nodes_to_start}")
        for node_id in nodes_to_start:
            # Enqueue the status change. The graph_worker will process this,
            # save the change, and emit the 'node_ready' event.
            MODIFICATION_QUEUE.put((
                edit.edit_status_in_graph,
                (abs_path, "node", node_id, "run"),
                {}
            ))
            
        return current_app.json.response({"status": "started"}), 202

    # ============================================================
    #  PIPELINE EXECUTION LOGIC (MOVED FROM RUN.PY)
    # ============================================================

    # ------------------------------------------------------------
    # RUN SERVER
    # ------------------------------------------------------------
    try:
        socketio.run(app, port=port)
    finally:
        reg = utils.load_registry()
        reg.pop(abs_path, None)
        utils.save_registry(reg)
        log.info("Server shut down cleanly; registry updated.")


# ============================================================
# CLI BRIDGE
# ============================================================
def cmd_start(args):
    start_server(args.filename or utils.default_workfile(), port=args.port, background=not args.foreground)

def cmd_stop(args):
    stop_server(args.filename or utils.default_workfile())

def cmd_list(args):
    list_servers()
