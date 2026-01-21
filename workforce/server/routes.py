import uuid
import logging
import os
import signal
from flask import current_app, request, g, jsonify
from workforce import edit
import networkx as nx

log = logging.getLogger(__name__)

def serialize_graph_lightweight(G):
    """Serialize graph excluding heavyweight attributes (logs, wrapper).
    
    Returns node-link format with only essential rendering data:
    - nodes: id, label, x, y, status (excludes log, stdout, stderr, pid, etc.)
    - links: source, target, id, status
    - graph: empty dict (no wrapper)
    """
    data = nx.node_link_data(G, edges="links")
    
    # Strip heavyweight attributes from nodes
    heavyweight_attrs = {"log", "stdout", "stderr", "pid", "command", "error_code"}
    for node in data.get("nodes", []):
        for attr in heavyweight_attrs:
            node.pop(attr, None)
    
    # Remove wrapper from graph metadata
    data["graph"] = {}
    
    return data


def _kill_nodes_for_run(ctx, run_id: str) -> dict:
    """Kill running processes for a specific run and mark nodes as failed."""
    from workforce import edit

    try:
        G = edit.load_graph(ctx.workfile_path)
    except Exception:
        return {"killed": 0, "errors": ["graph_load_failed"], "stopped_nodes": []}

    running_nodes = []
    killed = 0
    errors = []

    for node_id, attrs in G.nodes(data=True):
        if attrs.get("status") != "running":
            continue
        mapped_run = ctx.active_node_run.get(node_id)
        if mapped_run and mapped_run != run_id:
            continue

        running_nodes.append(node_id)
        pid_raw = attrs.get("pid", "")
        pid_str = str(pid_raw).strip() if pid_raw is not None else ""
        if pid_str.isdigit():
            try:
                os.kill(int(pid_str), signal.SIGKILL)
                killed += 1
            except Exception as e:
                errors.append(f"{node_id}:{pid_str}:{e}")

    for node_id in running_nodes:
        ctx.enqueue_status(ctx.workfile_path, "node", node_id, "fail", run_id)
        ctx.active_node_run.pop(node_id, None)

    return {"killed": killed, "errors": errors, "stopped_nodes": running_nodes}

def register_routes(app):
    """Register all routes with workspace routing middleware."""
    
    # Import here to avoid circular dependency
    from workforce.server import (
        get_context,
        get_or_create_context,
        destroy_context,
        _contexts,
        _contexts_lock,
        _clean_workspace_cache,
        _stop_nodes_for_workspace,
    )
    from workforce.utils import compute_workspace_id
    
    @app.route("/health", methods=["GET"])
    def health():
        return {"status": "ok"}, 200

    @app.before_request
    def extract_workspace_id():
        """Extract workspace_id from URL and load context into g."""
        path_parts = request.path.strip('/').split('/')
        
        # Check if this is a workspace-routed request
        if len(path_parts) >= 2 and path_parts[0] == 'workspace':
            workspace_id = path_parts[1]
            g.workspace_id = workspace_id
            g.ctx = get_context(workspace_id)
        elif request.path == '/workspaces':
            # Diagnostic endpoint, no context needed
            pass
        else:
            g.workspace_id = None
            g.ctx = None
    
    @app.route("/workspaces", methods=["GET"])
    def list_workspaces():
        """Diagnostic endpoint: list active workspaces."""
        # Import inside to avoid circulars at import time
        from workforce.server import get_bind_info
        bind_host, bind_port = get_bind_info()
        lan_enabled = bool(bind_host and bind_host not in ("127.0.0.1", "localhost"))
        workspaces = []
        # Read contexts under lock to avoid race conditions with concurrent connect/disconnect
        with _contexts_lock:
            for ws_id, ctx in _contexts.items():
                summary = ctx.client_summary
                workspaces.append({
                    "workspace_id": ws_id,
                    "workfile_path": ctx.workfile_path,
                    "client_count": summary.get("gui", 0) + summary.get("runner", 0),
                    "clients": summary,
                    "created_at": ctx.created_at,
                })
        return jsonify({
            "server": {
                "host": bind_host,
                "port": bind_port,
                "lan_enabled": lan_enabled,
            },
            "workspaces": workspaces
        })

    @app.route("/workspace/register", methods=["POST"])
    def register_workspace():
        data = request.get_json(force=True)
        path = data.get("path") or data.get("workfile_path")
        if not path:
            return jsonify({"error": "path required"}), 400

        abs_path = os.path.abspath(path)
        workspace_id = compute_workspace_id(abs_path)

        # Ensure graph exists to avoid late failures
        try:
            edit.load_graph(abs_path)
        except Exception as e:
            return jsonify({"error": f"Failed to load graph: {e}"}), 500

        ctx = get_or_create_context(workspace_id, abs_path)

        from workforce.server import get_bind_info
        host, port = get_bind_info()
        if not host or not port:
            # Fallback if bind info not yet set
            host = "127.0.0.1"
            port = 5000
        url = f"http://{host}:{port}/workspace/{workspace_id}"

        return jsonify({
            "workspace_id": workspace_id,
            "url": url,
            "path": abs_path,
            "client_count": ctx.client_summary.get("gui", 0) + ctx.client_summary.get("runner", 0),
            "clients": ctx.client_summary,
        }), 200
    
    @app.route("/workspace/<workspace_id>/get-graph", methods=["GET"])
    def get_graph(workspace_id):
        ctx = g.ctx
        if not ctx:
            return jsonify({"error": "Workspace not found"}), 404
        
        G = edit.load_graph(ctx.workfile_path)
        data = nx.node_link_data(G, edges="links")
        
        # Strip heavyweight attributes from nodes (logs)
        heavyweight_attrs = {"log", "stdout", "stderr", "pid", "command", "error_code"}
        for node in data.get("nodes", []):
            for attr in heavyweight_attrs:
                node.pop(attr, None)
        
        # Include wrapper in initial load
        data["graph"] = G.graph
        data["graph"].setdefault("wrapper", "{}")
        return jsonify(data)

    @app.route("/workspace/<workspace_id>/get-node-log/<node_id>", methods=["GET"])
    def get_node_log(workspace_id, node_id):
        ctx = g.ctx
        if not ctx:
            return jsonify({"error": "Workspace not found"}), 404
        
        G = edit.load_graph(ctx.workfile_path)
        if node_id in G.nodes:
            node = G.nodes[node_id]
            
            # Check if node has new structured execution data
            if any(key in node for key in ["command", "stdout", "stderr", "pid", "error_code"]):
                command = node.get("command", "")
                stdout = node.get("stdout", "")
                stderr = node.get("stderr", "")
                pid = node.get("pid", "")
                error_code = node.get("error_code", "")
                
                # Format as requested: COMMAND:\n... STDOUT:\n... STDERR:\n... PID:\n... Error code:\n...
                log_text = f"COMMAND:\n{command}\n\nSTDOUT:\n{stdout}\n\nSTDERR:\n{stderr}\n\nPID:\n{pid}\n\nError code:\n{error_code}"
                return jsonify({"log": log_text})
            
            # Fallback to old log format if present
            if "log" in node:
                log_text = node.get("log", "[No log available for this node]")
                return jsonify({"log": log_text})
            
            return jsonify({"log": "[No log available for this node]"})
        else:
            return jsonify({"error": "Node not found"}), 404

    @app.route("/workspace/<workspace_id>/add-node", methods=["POST"])
    def add_node(workspace_id):
        ctx = g.ctx
        if not ctx:
            return jsonify({"error": "Workspace not found"}), 404
        
        data = request.get_json(force=True)
        # Extract idempotency key from header or request data
        idempotency_key = request.headers.get("X-Idempotency-Key") or data.get("idempotency_key")
        result = ctx.enqueue(
            edit.add_node_to_graph,
            ctx.workfile_path,
            data["label"],
            data.get("x", 0),
            data.get("y", 0),
            data.get("status", ""),
            idempotency_key=idempotency_key
        )
        return jsonify(result), 202

    @app.route("/workspace/<workspace_id>/remove-node", methods=["POST"])
    def remove_node(workspace_id):
        ctx = g.ctx
        if not ctx:
            return jsonify({"error": "Workspace not found"}), 404
        
        data = request.get_json(force=True)
        result = ctx.enqueue(edit.remove_node_from_graph, ctx.workfile_path, data["node_id"])
        return jsonify(result), 202

    @app.route("/workspace/<workspace_id>/add-edge", methods=["POST"])
    def add_edge(workspace_id):
        ctx = g.ctx
        if not ctx:
            return jsonify({"error": "Workspace not found"}), 404
        
        data = request.get_json(force=True)
        result = ctx.enqueue(
            edit.add_edge_to_graph,
            ctx.workfile_path,
            data["source"],
            data["target"],
            data.get("edge_type", "blocking")
        )
        return jsonify(result), 202

    @app.route("/workspace/<workspace_id>/edit-edge-type", methods=["POST"])
    def edit_edge_type(workspace_id):
        ctx = g.ctx
        if not ctx:
            return jsonify({"error": "Workspace not found"}), 404
        
        data = request.get_json(force=True)
        result = ctx.enqueue(
            edit.edit_edge_type_in_graph,
            ctx.workfile_path,
            data["source"],
            data["target"],
            data.get("edge_type", "blocking")
        )
        return jsonify(result), 202

    @app.route("/workspace/<workspace_id>/remove-edge", methods=["POST"])
    def remove_edge(workspace_id):
        ctx = g.ctx
        if not ctx:
            return jsonify({"error": "Workspace not found"}), 404
        
        data = request.get_json(force=True)
        result = ctx.enqueue(edit.remove_edge_from_graph, ctx.workfile_path, data["source"], data["target"])
        return jsonify(result), 202

    @app.route("/workspace/<workspace_id>/edit-status", methods=["POST"])
    def edit_status(workspace_id):
        ctx = g.ctx
        if not ctx:
            return jsonify({"error": "Workspace not found"}), 404
        
        data = request.get_json(force=True)
        result = ctx.enqueue_status(
            ctx.workfile_path, data["element_type"], data["element_id"],
            data.get("value", ""), data.get("run_id")
        )
        return jsonify(result), 202

    @app.route("/workspace/<workspace_id>/edit-statuses", methods=["POST"])
    def edit_statuses(workspace_id):
        """Batch update statuses for multiple elements (nodes/edges)."""
        ctx = g.ctx
        if not ctx:
            return jsonify({"error": "Workspace not found"}), 404
        
        data = request.get_json(force=True)
        updates = data.get("updates", [])
        
        if not updates:
            return jsonify({"error": "updates array required"}), 400
        
        # Queue batch operation (no run tracking for batch clears)
        result = ctx.enqueue(
            edit.edit_statuses_in_graph,
            ctx.workfile_path,
            updates
        )
        return jsonify(result), 202

    @app.route("/workspace/<workspace_id>/remove-node-logs", methods=["POST"])
    def remove_node_logs(workspace_id):
        """Remove execution logs from multiple nodes."""
        ctx = g.ctx
        if not ctx:
            return jsonify({"error": "Workspace not found"}), 404
        
        data = request.get_json(force=True)
        node_ids = data.get("node_ids", [])
        
        if not node_ids:
            return jsonify({"error": "node_ids array required"}), 400
        
        result = ctx.enqueue(
            edit.remove_node_logs_in_graph,
            ctx.workfile_path,
            node_ids
        )
        return jsonify(result), 202

    @app.route("/workspace/<workspace_id>/edit-node-position", methods=["POST"])
    def edit_node_position(workspace_id):
        ctx = g.ctx
        if not ctx:
            return jsonify({"error": "Workspace not found"}), 404
        
        data = request.get_json(force=True)
        result = ctx.enqueue(
            edit.edit_node_position_in_graph,
            ctx.workfile_path,
            data["node_id"],
            data["x"],
            data["y"]
        )
        return jsonify(result), 202

    @app.route("/workspace/<workspace_id>/edit-node-positions", methods=["POST"])
    def edit_node_positions(workspace_id):
        """Batch update positions for multiple nodes."""
        ctx = g.ctx
        if not ctx:
            return jsonify({"error": "Workspace not found"}), 404
        
        data = request.get_json(force=True)
        positions = data.get("positions", [])
        
        if not positions:
            return jsonify({"error": "positions array required"}), 400
        
        result = ctx.enqueue(
            edit.edit_node_positions_in_graph,
            ctx.workfile_path,
            positions
        )
        return jsonify(result), 202

    @app.route("/workspace/<workspace_id>/edit-wrapper", methods=["POST"])
    def edit_wrapper(workspace_id):
        ctx = g.ctx
        if not ctx:
            return jsonify({"error": "Workspace not found"}), 404
        
        data = request.get_json(force=True)
        result = ctx.enqueue(edit.edit_wrapper_in_graph, ctx.workfile_path, data.get("wrapper"))
        return jsonify(result), 202

    @app.route("/workspace/<workspace_id>/edit-node-label", methods=["POST"])
    def edit_node_label(workspace_id):
        ctx = g.ctx
        if not ctx:
            return jsonify({"error": "Workspace not found"}), 404
        
        data = request.get_json(force=True)
        result = ctx.enqueue(edit.edit_node_label_in_graph, ctx.workfile_path, data["node_id"], data["label"])
        return jsonify(result), 202

    @app.route("/workspace/<workspace_id>/save-node-log", methods=["POST"])
    def save_node_log_api(workspace_id):
        ctx = g.ctx
        if not ctx:
            return jsonify({"error": "Workspace not found"}), 404
        
        data = request.get_json(force=True)
        
        # Handle both old format (single "log" field) and new format (structured fields)
        if "log" in data and len(data) == 2:  # Old format: node_id + log
            # Backward compatibility: single log string
            result = ctx.enqueue(edit.save_node_log_in_graph, ctx.workfile_path, data["node_id"], data["log"])
        else:
            # New format: structured execution data
            result = ctx.enqueue(
                edit.save_node_execution_data_in_graph,
                ctx.workfile_path,
                data.get("node_id"),
                data.get("command", ""),
                data.get("stdout", ""),
                data.get("stderr", ""),
                data.get("pid", ""),
                data.get("error_code", "")
            )
        return jsonify(result), 202

    @app.route("/workspace/<workspace_id>/client-connect", methods=["POST"])
    def client_connect(workspace_id):
        """Called when a client connects. Creates context if needed.
        Defaults to GUI client when client_type is omitted.
        """
        try:
            data = request.get_json(force=True) if request.data else {}
            workfile_path = data.get("workfile_path")
            client_type = (data.get("client_type") or "gui").lower()
            socketio_sid = data.get("socketio_sid")

            if not workfile_path:
                return jsonify({"error": "workfile_path required"}), 400

            ctx = get_or_create_context(workspace_id, workfile_path)

            if client_type == "gui":
                client_id = str(uuid.uuid4())
                ctx.add_gui_client(client_id, socketio_sid)
            elif client_type == "runner":
                # Runner clients register via /run; accept but do not add here
                client_id = None
            else:
                # Unknown client type, default to GUI for backwards compatibility
                client_type = "gui"
                client_id = str(uuid.uuid4())
                ctx.add_gui_client(client_id, socketio_sid)

            return jsonify({"status": "connected", "workspace_id": workspace_id, "client_id": client_id, "client_type": client_type}), 200
        except Exception as e:
            log.exception("Error in client_connect: %s", e)
            return jsonify({"error": str(e)}), 500

    @app.route("/workspace/<workspace_id>/client-disconnect", methods=["POST"])
    def client_disconnect(workspace_id):
        """Called when a client disconnects. Destroys context if no clients remain.
        If client_type/client_id are omitted and exactly one GUI client exists, remove it.
        """
        try:
            ctx = get_context(workspace_id)
            if not ctx:
                return jsonify({"status": "disconnected"}), 200

            data = request.get_json(force=True) if request.data else {}
            client_type = data.get("client_type")
            client_id = data.get("client_id")

            # Explicit removal when identifiers provided
            if client_type == "gui" and client_id:
                ctx.remove_gui_client(client_id)
            elif client_type == "runner" and client_id:
                _kill_nodes_for_run(ctx, client_id)
                ctx.remove_runner_client(client_id)
                ctx.active_runs.pop(client_id, None)
                to_remove = [nid for nid, rid in ctx.active_node_run.items() if rid == client_id]
                for nid in to_remove:
                    ctx.active_node_run.pop(nid, None)
            else:
                # Fallback: if exactly one GUI client exists, remove it
                if len(ctx.gui_clients) == 1 and len(ctx.runner_clients) == 0:
                    only_id = next(iter(ctx.gui_clients.keys()))
                    ctx.remove_gui_client(only_id)

            if ctx.should_destroy():
                destroy_context(workspace_id)
            return jsonify({"status": "disconnected", "workspace_id": workspace_id}), 200
        except Exception as e:
            log.exception("Error in client_disconnect: %s", e)
            return jsonify({"error": str(e)}), 500

    @app.route("/workspace/<workspace_id>/run", methods=["POST"])
    def run_pipeline(workspace_id):
        """Start or resume a workflow run."""
        try:
            ctx = g.ctx
            data = request.get_json(force=True) if request.data else {}
            if not ctx:
                workfile_path = data.get("workfile_path")
                if not workfile_path:
                    return jsonify({"error": "Workspace not found"}), 404
                ctx = get_or_create_context(workspace_id, workfile_path)
                g.ctx = ctx

            socketio_sid = data.get("socketio_sid")
            selected_nodes = data.get("nodes")

            # create run id and register
            run_id = str(uuid.uuid4())
            ctx.add_runner_client(run_id, socketio_sid)
            G = edit.load_graph(ctx.workfile_path)

            # Blocking cycle prevention (only consider blocking edges)
            if selected_nodes:
                # Build blocking-only subgraph restricted to selected nodes
                blocking_edges = [
                    (u, v, data) for u, v, data in G.edges(data=True)
                    if data.get("edge_type", "blocking") == "blocking" and u in selected_nodes and v in selected_nodes
                ]
                sub = nx.DiGraph()
                sub.add_nodes_from((n, G.nodes[n]) for n in selected_nodes if n in G)
                sub.add_edges_from(blocking_edges)
                has_cycle = not nx.is_directed_acyclic_graph(sub)
            else:
                has_cycle = edit.has_blocking_cycle(ctx.workfile_path)

            if has_cycle:
                return jsonify({"error": "Run blocked: blocking edges contain a cycle"}), 400

            # Determine which nodes to start and which are in scope for this run
            if selected_nodes:
                # Subset run: only run selected nodes in dependency order
                selected_set = set(selected_nodes)
                log.info("Starting subset run with selected nodes: %s", selected_nodes)
                
                # Create subgraph of only selected nodes
                subgraph = G.subgraph(selected_nodes)
                
                # Find root nodes: nodes with in-degree 0 in the subgraph
                nodes_to_start = [n for n, d in subgraph.in_degree() if d == 0]
                
                if not nodes_to_start:
                    log.warning("No root nodes found in subgraph, starting all selected nodes")
                    nodes_to_start = list(selected_nodes)
                
                log.info("Starting from subset roots (0 in-degree in subgraph): %s", nodes_to_start)
                # For subset runs, track exactly which nodes to execute
                ctx.active_runs[run_id] = {"nodes": selected_set, "subset_only": True}
            else:
                # Full pipeline run: all nodes from roots onwards
                # First try failed nodes
                failed_nodes = [n for n, attr in G.nodes(data=True) if attr.get("status") == "fail"]
                if failed_nodes:
                    nodes_to_start = failed_nodes
                    log.info("Resuming from failed nodes: %s", failed_nodes)
                else:
                    # Otherwise start from nodes with 0 in-degree AND no status (clean start)
                    nodes_to_start = [n for n, d in G.in_degree() if d == 0 and not G.nodes[n].get("status")]
                    if not nodes_to_start:
                        # If all root nodes have status, clear them and start
                        nodes_to_start = [n for n, d in G.in_degree() if d == 0]
                        log.info("Clearing status on root nodes: %s", nodes_to_start)
                        for node_id in nodes_to_start:
                            ctx.enqueue(edit.edit_status_in_graph, ctx.workfile_path, "node", node_id, "")
                    log.info("Starting from root nodes (0 in-degree): %s", nodes_to_start)
                # For full pipeline, don't restrict which nodes can run (empty "nodes" set means no restriction)
                ctx.active_runs[run_id] = {"nodes": set(), "subset_only": False}

            if not nodes_to_start:
                log.warning("No nodes to start the run.")
                return jsonify({"status": "no nodes to start", "run_id": run_id}), 200

            log.info("Queuing initial nodes for run %s: %s", run_id, nodes_to_start)
            for node_id in nodes_to_start:
                # Always clear status first, then set to 'run'
                ctx.enqueue(edit.edit_status_in_graph, ctx.workfile_path, "node", node_id, "")
                ctx.enqueue_status(ctx.workfile_path, "node", node_id, "run", run_id)

            return jsonify({"status": "started", "run_id": run_id, "client_id": run_id}), 202
        except Exception as e:
            log.exception("Error in /run endpoint")
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/workspace/<workspace_id>/clients", methods=["GET"])
    def list_clients(workspace_id):
        ctx = g.ctx
        if not ctx:
            return jsonify({"error": "Workspace not found"}), 404

        gui = []
        for gid, meta in ctx.gui_clients.items():
            gui.append({
                "client_id": gid,
                "connected_at": meta.get("connected_at"),
                "socketio_sid": meta.get("socketio_sid"),
            })

        runner = []
        try:
            G = edit.load_graph(ctx.workfile_path)
        except Exception:
            G = None

        for rid, meta in ctx.runner_clients.items():
            nodes_total = len(ctx.active_runs.get(rid, {}).get("nodes", set()) or []) or (len(G.nodes) if G else 0)
            nodes_running = 0
            nodes_failed = 0
            if G:
                for node_id, attrs in G.nodes(data=True):
                    if ctx.active_node_run.get(node_id) != rid:
                        continue
                    if attrs.get("status") == "running":
                        nodes_running += 1
                    if attrs.get("status") == "fail":
                        nodes_failed += 1
            runner.append({
                "client_id": rid,
                "run_id": rid,
                "connected_at": meta.get("connected_at"),
                "socketio_sid": meta.get("socketio_sid"),
                "nodes_total": nodes_total,
                "nodes_running": nodes_running,
                "nodes_failed": nodes_failed,
            })

        return jsonify({"gui": gui, "runner": runner})

    @app.route("/workspace/<workspace_id>/runs", methods=["GET"])
    def list_runs(workspace_id):
        ctx = g.ctx
        if not ctx:
            return jsonify({"error": "Workspace not found"}), 404

        runs = []
        try:
            G = edit.load_graph(ctx.workfile_path)
        except Exception:
            G = None

        for rid, meta in ctx.active_runs.items():
            nodes_scope = meta.get("nodes") or set()
            subset_only = bool(meta.get("subset_only"))
            nodes_running = 0
            nodes_failed = 0
            nodes_total = len(nodes_scope) if nodes_scope else (len(G.nodes) if G else 0)
            if G:
                for node_id, attrs in G.nodes(data=True):
                    if nodes_scope and node_id not in nodes_scope:
                        continue
                    if ctx.active_node_run.get(node_id) not in (None, rid) and ctx.active_node_run.get(node_id) != rid:
                        continue
                    if attrs.get("status") == "running":
                        nodes_running += 1
                    if attrs.get("status") == "fail":
                        nodes_failed += 1
            runs.append({
                "run_id": rid,
                "subset_only": subset_only,
                "nodes_total": nodes_total,
                "nodes_running": nodes_running,
                "nodes_failed": nodes_failed,
            })

        return jsonify({"runs": runs})

    @app.route("/workspace/<workspace_id>/stop", methods=["POST"])
    def stop_runs(workspace_id):
        """Stop all active runs: kill running processes and mark nodes as failed."""
        ctx = g.ctx
        if not ctx:
            return jsonify({"error": "Workspace not found"}), 404
        try:
            G = edit.load_graph(ctx.workfile_path)
            running_nodes = []
            killed = 0
            errors = []

            # Attempt to kill processes for nodes marked as running
            for node_id, attrs in G.nodes(data=True):
                if attrs.get("status") == "running":
                    running_nodes.append(node_id)
                    pid_raw = attrs.get("pid", "")
                    pid_str = str(pid_raw).strip() if pid_raw is not None else ""
                    if pid_str.isdigit():
                        try:
                            os.kill(int(pid_str), signal.SIGKILL)
                            killed += 1
                        except Exception as e:
                            errors.append(f"{node_id}:{pid_str}:{e}")

            # Mark all running nodes as failed (enqueue through worker)
            # This will prevent edge propagation since failed nodes don't mark outgoing edges
            for node_id in running_nodes:
                # Get the run_id for this node if it's being tracked
                run_id = ctx.active_node_run.get(node_id)
                ctx.enqueue_status(ctx.workfile_path, "node", node_id, "fail", run_id)

            log.info(f"Stop runs: killed {killed} processes, stopped {len(running_nodes)} nodes")
            return jsonify({
                "killed": killed,
                "errors": errors,
                "stopped_nodes": running_nodes
            }), 200
        except Exception as e:
            log.exception("Error in /stop endpoint")
            return jsonify({"error": str(e)}), 500

    @app.route("/workspace/<workspace_id>", methods=["DELETE"])
    def delete_workspace(workspace_id):
        """Remove a workspace context, stop active runs, and clear cache."""
        ctx = get_context(workspace_id)
        if ctx:
            _stop_nodes_for_workspace(workspace_id)
            destroy_context(workspace_id)
        _clean_workspace_cache(workspace_id)
        return jsonify({"status": "removed", "workspace_id": workspace_id}), 200

    @app.route("/workspace/<workspace_id>/save-as", methods=["POST"])
    def save_as(workspace_id):
        """Save current graph to a new file path."""
        ctx = g.ctx
        if not ctx:
            return jsonify({"error": "Workspace not found"}), 404
        
        # Check for active runs
        if ctx.active_runs:
            return jsonify({"error": "Cannot save during active workflow execution"}), 409
        
        data = request.get_json(force=True)
        new_path = data.get("new_path")
        
        if not new_path:
            return jsonify({"error": "new_path required"}), 400
        
        try:
            # Get absolute path
            new_path = os.path.abspath(new_path)
            
            # Load current graph (with all statuses intact) and save to new location
            G = edit.load_graph(ctx.workfile_path)
            edit.save_graph(G, new_path)
            
            # Compute new workspace identifiers
            from workforce.utils import compute_workspace_id, get_workspace_url
            new_workspace_id = compute_workspace_id(new_path)
            new_base_url = get_workspace_url(new_workspace_id)
            
            log.info(f"Saved workflow from {ctx.workfile_path} to {new_path} (new workspace: {new_workspace_id})")
            
            return jsonify({
                "status": "saved",
                "new_path": new_path,
                "new_workspace_id": new_workspace_id,
                "new_base_url": new_base_url
            }), 200
        except Exception as e:
            log.exception("Error in /save-as endpoint")
            return jsonify({"status": "error", "message": str(e)}), 500
