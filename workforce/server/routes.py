import uuid
import logging
import os
from flask import current_app, request, g, jsonify
from workforce import edit

log = logging.getLogger(__name__)

def register_routes(app):
    """Register all routes with workspace routing middleware."""
    
    # Import here to avoid circular dependency
    from workforce.server import get_context, get_or_create_context, destroy_context, _contexts
    
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
        workspaces = []
        for ws_id, ctx in _contexts.items():
            workspaces.append({
                "workspace_id": ws_id,
                "workfile_path": ctx.workfile_path,
                "client_count": ctx.client_count,
                "created_at": ctx.created_at,
            })
        return jsonify({"workspaces": workspaces})
    
    @app.route("/workspace/<workspace_id>/get-graph", methods=["GET"])
    def get_graph(workspace_id):
        ctx = g.ctx
        if not ctx:
            return jsonify({"error": "Workspace not found"}), 404
        
        G = edit.load_graph(ctx.workfile_path)
        data = __import__("networkx").node_link_data(G, edges="links")
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
            log_text = G.nodes[node_id].get("log", "[No log available for this node]")
            return jsonify({"log": log_text})
        else:
            return jsonify({"error": "Node not found"}), 404

    @app.route("/workspace/<workspace_id>/add-node", methods=["POST"])
    def add_node(workspace_id):
        ctx = g.ctx
        if not ctx:
            return jsonify({"error": "Workspace not found"}), 404
        
        data = request.get_json(force=True)
        result = ctx.enqueue(
            edit.add_node_to_graph,
            ctx.workfile_path,
            data["label"],
            data.get("x", 0),
            data.get("y", 0),
            data.get("status", "")
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
        result = ctx.enqueue(edit.add_edge_to_graph, ctx.workfile_path, data["source"], data["target"])
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
        result = ctx.enqueue(edit.save_node_log_in_graph, ctx.workfile_path, data["node_id"], data["log"])
        return jsonify(result), 202

    @app.route("/workspace/<workspace_id>/client-connect", methods=["POST"])
    def client_connect(workspace_id):
        """Called when a client connects. Creates context if needed."""
        try:
            data = request.get_json(force=True) if request.data else {}
            workfile_path = data.get("workfile_path")
            
            if not workfile_path:
                return jsonify({"error": "workfile_path required"}), 400
            
            # Create or get context
            ctx = get_or_create_context(workspace_id, workfile_path)
            ctx.increment_clients()
            
            log.info(f"Client connected to {workspace_id}; clients: {ctx.client_count}")
            return jsonify({"status": "connected", "workspace_id": workspace_id}), 200
        except Exception as e:
            log.exception("Error in client_connect: %s", e)
            return jsonify({"error": str(e)}), 500

    @app.route("/workspace/<workspace_id>/client-disconnect", methods=["POST"])
    def client_disconnect(workspace_id):
        """Called when a client disconnects. Destroys context if no clients remain."""
        try:
            ctx = get_context(workspace_id)
            if not ctx:
                return jsonify({"status": "disconnected"}), 200
            
            new_count = ctx.decrement_clients()
            log.info(f"Client disconnected from {workspace_id}; clients: {new_count}")
            
            # If no clients remain, destroy context
            if ctx.should_destroy():
                destroy_context(workspace_id)
                log.info(f"Destroyed context for {workspace_id} (no clients)")
            
            return jsonify({"status": "disconnected", "workspace_id": workspace_id}), 200
        except Exception as e:
            log.exception("Error in client_disconnect: %s", e)
            return jsonify({"error": str(e)}), 500

    @app.route("/workspace/<workspace_id>/run", methods=["POST"])
    def run_pipeline(workspace_id):
        """Start or resume a workflow run."""
        try:
            ctx = g.ctx
            if not ctx:
                return jsonify({"error": "Workspace not found"}), 404
            
            data = request.get_json(force=True) if request.data else {}
            selected_nodes = data.get("nodes")

            # create run id and register
            run_id = str(uuid.uuid4())
            G = edit.load_graph(ctx.workfile_path)

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

            return jsonify({"status": "started", "run_id": run_id}), 202
        except Exception as e:
            log.exception("Error in /run endpoint")
            return jsonify({"status": "error", "message": str(e)}), 500

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
