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

    # Track active runs and node->run mapping in-process
    ACTIVE_RUNS: dict = {}        # run_id -> {"nodes": set(...), "subset_only": bool}
    ACTIVE_NODE_RUN: dict = {}    # node_id -> run_id

    def enqueue_status(path, element_type, element_id, value, run_id=None):
        """
        Wrapper around edit.edit_status_in_graph that preserves run_id context for node 'run' events.
        It records node->run associations so the scheduler can track run completion and propagate events.
        """
        # Record the node's association to a run when it's queued to 'run'
        if run_id and element_type == "node" and value == "run":
            ACTIVE_NODE_RUN[element_id] = run_id
            ACTIVE_RUNS.setdefault(run_id, {"nodes": set(), "subset_only": False})["nodes"].add(element_id)
        return edit.edit_status_in_graph(path, element_type, element_id, value)

    def _check_and_trigger_successors(path, G, completed_node_id):
        """
        After a node completes, check its successors to see if they are ready to run.
        A successor is ready if all of its predecessors have a status of 'ran'.
        """
        log.info(f"Checking successors for node {completed_node_id}")
        if completed_node_id not in G:
            log.warning(f"Node {completed_node_id} not found in graph.")
            return

        for successor in G.successors(completed_node_id):
            predecessors = list(G.predecessors(successor))
            log.info(f"Successor {successor} has predecessors: {predecessors}")
            all_deps_met = all(
                G.nodes[p].get("status") == "ran" for p in predecessors
            )

            if all_deps_met:
                log.info(f"All dependencies for '{successor}' are met. Queuing it to run.")
                MODIFICATION_QUEUE.put((edit.edit_status_in_graph, (path, "node", successor, "run"), {}))
            else:
                log.info(f"Dependencies not met for '{successor}'. Waiting for other predecessors.")

    def execute_node_on_server(node_id, label):
        """
        Executes a node's command directly on the server.
        This is triggered when a remote run is requested without a dedicated runner client.
        """
        log.info(f"--> Server executing node: {label} ({node_id})")
        try:
            # Use the graph's wrapper, not a locally passed one
            G = edit.load_graph(abs_path)
            wrapper = G.graph.get('wrapper', '{}')

            # Enqueue status change to 'running'
            MODIFICATION_QUEUE.put((edit.edit_status_in_graph, (abs_path, "node", node_id, "running"), {}))

            if "{}" in wrapper:
                command = wrapper.replace("{}", utils.shell_quote_multiline(label))
            else:
                command = f"{wrapper} {utils.shell_quote_multiline(label)}"

            if not command.strip():
                log.info(f"--> Empty command for {node_id}, marking done.")
                MODIFICATION_QUEUE.put((edit.save_node_log_in_graph, (abs_path, node_id, "[No command to run]"), {}))
                MODIFICATION_QUEUE.put((edit.edit_status_in_graph, (abs_path, "node", node_id, "ran"), {}))
                return

            process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            stdout, stderr = process.communicate()

            log_text = f"{stdout}\n{stderr}".strip()
            MODIFICATION_QUEUE.put((edit.save_node_log_in_graph, (abs_path, node_id, log_text), {}))

            if process.returncode == 0:
                log.info(f"--> Server finished node: {label} ({node_id})")
                MODIFICATION_QUEUE.put((edit.edit_status_in_graph, (abs_path, "node", node_id, "ran"), {}))
            else:
                log.warning(f"!! Server failed node: {label} ({node_id})")
                MODIFICATION_QUEUE.put((edit.edit_status_in_graph, (abs_path, "node", node_id, "fail"), {}))

        except Exception as e:
            log.error(f"!! Server error executing {node_id}: {e}", exc_info=True)
            MODIFICATION_QUEUE.put((edit.edit_status_in_graph, (abs_path, "node", node_id, "fail"), {}))

    # ------------------------------------------------------------
    # GRAPH WORKER — simplified, no diffing, always emits lifecycle
    # ------------------------------------------------------------
    def graph_worker():
        log.info("Graph worker thread started.")
        while True:
            func, args, kwargs = MODIFICATION_QUEUE.get()
            try:
                result = func(*args, **kwargs)
                
                # After any modification, reload the graph to get the latest state
                G = edit.load_graph(args[0])  # args[0] is the path
                data = nx.node_link_data(G, edges="links")
                data["graph"] = G.graph

                # Always broadcast the new graph state to all clients
                log.debug(f"Emitting graph_update for {args[0]}")
                socketio.emit("graph_update", data, namespace="/")

                # Lifecycle handling: consider status changes (either from edit_status_in_graph or enqueue_status)
                if func.__name__ in ('edit_status_in_graph', 'enqueue_status'):
                    # Unpack args. enqueue_status signature: (path, element_type, element_id, value, run_id)
                    if func.__name__ == 'enqueue_status':
                        _, el_type, el_id, status, run_id = args
                    else:
                        _, el_type, el_id, status = args
                        run_id = ACTIVE_NODE_RUN.get(el_id)

                    # Node becomes ready-to-run (status == 'run')
                    if el_type == 'node' and status == 'run':
                        # If running on server, execute here; otherwise tell runner clients.
                        if G.graph.get('run_on_server', False):
                            label = G.nodes[el_id].get('label', '')
                            threading.Thread(target=execute_node_on_server, args=(el_id, label), daemon=True).start()
                        else:
                            socketio.emit("node_ready", {"node_id": el_id, "label": G.nodes[el_id].get('label', ''), "run_id": run_id})
                    # Node finished
                    elif el_type == 'node' and status == 'ran':
                        # When a node completes, mark outgoing edges as 'ready' for this run
                        for _, tgt, edata in G.out_edges(el_id, data=True):
                            eid = edata.get('id')
                            if eid and edata.get('status') != 'ready':
                                # Tag the edge ready. pass run_id through as well (for later propagation)
                                MODIFICATION_QUEUE.put((enqueue_status, (args[0], "edge", eid, "ready", run_id), {}))

                        # Remove node from active-run tracking
                        if run_id:
                            ACTIVE_RUNS.get(run_id, {"nodes": set()})["nodes"].discard(el_id)
                            ACTIVE_NODE_RUN.pop(el_id, None)

                    # Edge became 'ready' — check its target node to see if all inputs are ready
                    elif el_type == 'edge' and status == 'ready':
                        # Find the edge endpoints by id
                        edge_end = None
                        for u, v, ed in G.edges(data=True):
                            if ed.get('id') == el_id:
                                edge_end = (u, v)
                                break
                        if edge_end:
                            u, v = edge_end
                            # Check all incoming edges for v
                            in_edges = list(G.in_edges(v, data=True))
                            all_ready = all(ed.get('status') == 'ready' for _, _, ed in in_edges)
                            if all_ready:
                                # Determine run_id for this triggering (prefer existing mapping from predecessors)
                                candidate_run_id = None
                                for uu, _, _ in in_edges:
                                    candidate_run_id = ACTIVE_NODE_RUN.get(uu)
                                    if candidate_run_id:
                                        break
                                # Clear incoming edges statuses
                                for _, _, ed in in_edges:
                                    eid2 = ed.get('id')
                                    if eid2 and ed.get('status') != "":
                                        MODIFICATION_QUEUE.put((enqueue_status, (args[0], "edge", eid2, "", candidate_run_id), {}))
                                # Only start target node if it's not already running/ran
                                node_status = G.nodes[v].get('status', '')
                                if node_status not in ("run", "running", "ran"):
                                    MODIFICATION_QUEUE.put((enqueue_status, (args[0], "node", v, "run", candidate_run_id), {}))

            except Exception as e:
                log.error(f"Graph worker error: {e}", exc_info=True)

            finally:
                MODIFICATION_QUEUE.task_done()

                # After a task is done, if the queue is empty, check for run completion.
                if MODIFICATION_QUEUE.empty():
                    def check_completion_task():
                        socketio.sleep(1.0)  # Wait a moment to see if new tasks arrive
                        if not MODIFICATION_QUEUE.empty():
                            return
                        # Inspect active runs: if none of their tracked nodes are still 'run'/'running', mark run complete
                        try:
                            G_local = edit.load_graph(abs_path)
                        except Exception:
                            return
                        for run_id in list(ACTIVE_RUNS.keys()):
                            nodes_set = set(ACTIVE_RUNS.get(run_id, {}).get("nodes", set()))
                            if not nodes_set:
                                # No nodes tracked anymore => complete
                                log.info("Run complete (no tracked nodes). Emitting run_complete for %s", run_id)
                                socketio.emit("run_complete", {"run_id": run_id})
                                ACTIVE_RUNS.pop(run_id, None)
                                # clean any residual mapping entries
                                for n, rid in list(ACTIVE_NODE_RUN.items()):
                                    if rid == run_id:
                                        ACTIVE_NODE_RUN.pop(n, None)
                                continue
                            # check current status for nodes in this run
                            still_running = any(
                                G_local.nodes[n].get("status") in ("run", "running")
                                for n in nodes_set if n in G_local.nodes
                            )
                            if not still_running:
                                log.info("Run complete (no running nodes) for %s. Emitting run_complete.", run_id)
                                socketio.emit("run_complete", {"run_id": run_id})
                                ACTIVE_RUNS.pop(run_id, None)
                                for n in list(nodes_set):
                                    ACTIVE_NODE_RUN.pop(n, None)

                    socketio.start_background_task(check_completion_task)

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
    def on_connect(auth=None):
        log.info("SocketIO client connected: %s", request.sid)
        # Previously: auto-trigger runs if client passed initial_nodes in auth.
        # That behavior caused runs to start on connect. Do NOT auto-start runs here.
        # Keep the handler minimal and let clients explicitly POST /run to start execution.
        # Optionally record client info in future if needed.

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
        data = nx.node_link_data(G, edges="links")
        data["graph"] = G.graph
        data["graph"].setdefault("prefix", "")
        data["graph"].setdefault("suffix", "")
        return current_app.json.response(data)

    @app.route("/get-node-log/<node_id>")
    def get_node_log(node_id):
        G = edit.load_graph(abs_path)
        if node_id in G.nodes:
            log_text = G.nodes[node_id].get("log", "[No log available for this node]")
            return current_app.json.response({"log": log_text})
        else:
            return current_app.json.response({"error": "Node not found"}, status=404)

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
        selected_nodes = data.get("nodes")
        run_on_server = data.get("run_on_server", False)
        subset_only = data.get("subset_only", False)
        start_failed = data.get("start_failed", False)

        G = edit.load_graph(abs_path)

        # Create run id and register the run
        run_id = str(uuid.uuid4())
        ACTIVE_RUNS[run_id] = {"nodes": set(), "subset_only": subset_only}

        G.graph['run_on_server'] = run_on_server

        graph_to_run = G.copy()

        if subset_only and selected_nodes:
            # Build a subgraph from the selected nodes
            log.info(f"Running on a subset of nodes: {selected_nodes}")
            graph_to_run = G.subgraph(selected_nodes).copy()

        nodes_to_start = []
        if not subset_only and selected_nodes:
            # Full graph run, but starting from specific nodes
            nodes_to_start = selected_nodes
        else:
            # Start all root nodes (in-degree 0) in the relevant graph (full or subgraph)
            nodes_to_start = [n for n, d in graph_to_run.in_degree() if d == 0]

        # If asked to start_failed, prefer failed nodes when no selection was provided
        if start_failed and (not selected_nodes):
            failed_nodes = [n for n, d in G.nodes(data=True) if d.get("status") == "fail"]
            if failed_nodes:
                nodes_to_start = failed_nodes
                log.info("Starting run from failed nodes: %s", failed_nodes)

        if not nodes_to_start:
            # This can happen if a cycle is selected or if all nodes have parents
            if selected_nodes:
                log.warning("Run requested for selected nodes, but none are root nodes in the selection. Starting them anyway.")
                nodes_to_start = selected_nodes
            else:
                log.warning("No root nodes found to start the run.")
                return current_app.json.response({"status": "no nodes to start"}), 200
            
        log.info(f"Queuing initial nodes for run {run_id}: {nodes_to_start}")
        for node_id in nodes_to_start:
            # Use enqueue_status so the association to run_id is recorded
            MODIFICATION_QUEUE.put((
                enqueue_status,
                (abs_path, "node", node_id, "run", run_id),
                {}
            ))
            
        # Return run_id so clients (runners) can filter events for this run
        return current_app.json.response({"status": "started", "run_id": run_id}), 202

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
