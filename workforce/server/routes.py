import uuid
import logging
from flask import current_app, request
from workforce import edit

log = logging.getLogger(__name__)

def register_routes(app, ctx):
    @app.route("/get-graph")
    def get_graph():
        G = edit.load_graph(ctx.path)
        data = __import__("networkx").node_link_data(G, edges="links")
        data["graph"] = G.graph
        data["graph"].setdefault("wrapper", "{}")
        return current_app.json.response(data)

    @app.route("/get-node-log/<node_id>")
    def get_node_log(node_id):
        G = edit.load_graph(ctx.path)
        if node_id in G.nodes:
            log_text = G.nodes[node_id].get("log", "[No log available for this node]")
            return current_app.json.response({"log": log_text})
        else:
            return current_app.json.response({"error": "Node not found"}, status=404)

    @app.route("/add-node", methods=["POST"])
    def add_node():
        data = request.get_json(force=True)
        return current_app.json.response(ctx.enqueue(edit.add_node_to_graph, ctx.path, data["label"], data.get("x", 0), data.get("y", 0), data.get("status", ""))), 202

    @app.route("/remove-node", methods=["POST"])
    def remove_node():
        data = request.get_json(force=True)
        return current_app.json.response(ctx.enqueue(edit.remove_node_from_graph, ctx.path, data["node_id"])), 202

    @app.route("/add-edge", methods=["POST"])
    def add_edge():
        data = request.get_json(force=True)
        return current_app.json.response(ctx.enqueue(edit.add_edge_to_graph, ctx.path, data["source"], data["target"])), 202

    @app.route("/remove-edge", methods=["POST"])
    def remove_edge():
        data = request.get_json(force=True)
        return current_app.json.response(ctx.enqueue(edit.remove_edge_from_graph, ctx.path, data["source"], data["target"])), 202

    @app.route("/edit-status", methods=["POST"])
    def edit_status():
        data = request.get_json(force=True)
        return current_app.json.response(ctx.enqueue_status(ctx.path, data["element_type"], data["element_id"], data.get("value", ""), data.get("run_id"))), 202

    @app.route("/edit-node-position", methods=["POST"])
    def edit_node_position():
        data = request.get_json(force=True)
        return current_app.json.response(ctx.enqueue(edit.edit_node_position_in_graph, ctx.path, data["node_id"], data["x"], data["y"])), 202

    @app.route("/edit-wrapper", methods=["POST"])
    def edit_wrapper():
        data = request.get_json(force=True)
        return current_app.json.response(ctx.enqueue(edit.edit_wrapper_in_graph, ctx.path, data.get("wrapper"))), 202

    @app.route("/edit-node-label", methods=["POST"])
    def edit_node_label():
        data = request.get_json(force=True)
        return current_app.json.response(ctx.enqueue(edit.edit_node_label_in_graph, ctx.path, data["node_id"], data["label"])), 202

    @app.route("/save-node-log", methods=["POST"])
    def save_node_log_api():
        data = request.get_json(force=True)
        return current_app.json.response(ctx.enqueue(edit.save_node_log_in_graph, ctx.path, data["node_id"], data["log"])), 202

    @app.route("/client-connect", methods=["POST"])
    def client_connect():
        try:
            return current_app.json.response({"status": "connected"}), 200
        except Exception:
            return "", 204

    @app.route("/client-disconnect", methods=["POST"])
    def client_disconnect():
        try:
            return current_app.json.response({"status": "disconnected"}), 200
        except Exception:
            return "", 204

    @app.route("/run", methods=["POST"])
    def run_pipeline():
        try:
            data = request.get_json(force=True) if request.data else {}
            selected_nodes = data.get("nodes")

            # create run id and register
            run_id = str(uuid.uuid4())
            G = edit.load_graph(ctx.path)

            # Determine which nodes to start and which are in scope for this run
            if selected_nodes:
                # Subset run: only run selected nodes in dependency order
                selected_set = set(selected_nodes)
                log.info("Starting subset run with selected nodes: %s", selected_nodes)
                
                # Create subgraph of only selected nodes
                subgraph = G.subgraph(selected_nodes)
                
                # Debug: log subgraph structure
                log.info(f"Subgraph has {subgraph.number_of_nodes()} nodes and {subgraph.number_of_edges()} edges")
                in_degrees = dict(subgraph.in_degree())
                log.info(f"In-degrees in subgraph: {in_degrees}")
                
                # Find root nodes: nodes with in-degree 0 in the subgraph
                nodes_to_start = [n for n, d in subgraph.in_degree() if d == 0]
                
                if not nodes_to_start:
                    log.warning("No root nodes found in subgraph, starting all selected nodes")
                    nodes_to_start = list(selected_nodes)
                
                log.info("Starting from subset roots (0 in-degree in subgraph): %s", nodes_to_start)
                # For subset runs, track exactly which nodes to execute
                ctx.active_runs[run_id] = {"nodes": selected_set}
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
                            ctx.enqueue(edit.edit_status_in_graph, ctx.path, "node", node_id, "")
                    log.info("Starting from root nodes (0 in-degree): %s", nodes_to_start)
                # For full pipeline, track all nodes
                ctx.active_runs[run_id] = {"nodes": set(G.nodes())}

            if not nodes_to_start:
                log.warning("No nodes to start the run.")
                return current_app.json.response({"status": "no nodes to start", "run_id": run_id}), 200

            log.info("Queuing initial nodes for run %s: %s", run_id, nodes_to_start)
            for node_id in nodes_to_start:
                # Always clear status first, then set to 'run'
                ctx.enqueue(edit.edit_status_in_graph, ctx.path, "node", node_id, "")
                ctx.enqueue_status(ctx.path, "node", node_id, "run", run_id)

            return current_app.json.response({"status": "started", "run_id": run_id}), 202
        except Exception as e:
            log.exception("Error in /run endpoint")
            return current_app.json.response({"status": "error", "message": str(e)}), 500
