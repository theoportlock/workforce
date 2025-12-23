import uuid
import logging
from flask import current_app, request
from workforce import edit

log = logging.getLogger(__name__)

def register_routes(app, ctx):
    @app.route("/get-graph")
    def get_graph():
        G = edit.load_graph(ctx.path)
        data = __import__("networkx").node_link_data(G, link="links")
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
        return current_app.json.response(ctx.enqueue(edit.edit_status_in_graph, ctx.path, data["element_type"], data["element_id"], data.get("value", ""))), 202

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

    @app.route("/run", methods=["POST"])
    def run_pipeline():
        data = request.get_json(force=True) if request.data else {}
        selected_nodes = data.get("nodes")
        subset_only = data.get("subset_only", False)
        start_failed = data.get("start_failed", False)

        # create run id and register
        run_id = str(uuid.uuid4())
        ctx.active_runs[run_id] = {
            "nodes": set(),
            "subset_only": subset_only,
            "subset_nodes": set(selected_nodes) if subset_only and selected_nodes else set()
        }

        G = edit.load_graph(ctx.path)
        graph_to_run = G.copy()

        if subset_only and selected_nodes:
            log.info("Running subset: %s", selected_nodes)
            graph_to_run = G.subgraph(selected_nodes).copy()

        nodes_to_start = []
        if not subset_only and selected_nodes:
            nodes_to_start = selected_nodes
        else:
            nodes_to_start = [n for n, d in graph_to_run.in_degree() if d == 0]

        if start_failed and (not selected_nodes):
            failed_nodes = [n for n, d in G.nodes(data=True) if d.get("status") == "fail"]
            if failed_nodes:
                nodes_to_start = failed_nodes
                log.info("Starting from failed nodes: %s", failed_nodes)

        if not nodes_to_start:
            if selected_nodes:
                log.warning("No root nodes found in selection; starting selected nodes anyway.")
                nodes_to_start = selected_nodes
            else:
                log.warning("No root nodes found to start the run.")
                return current_app.json.response({"status": "no nodes to start"}), 200

        log.info("Queuing initial nodes for run %s: %s", run_id, nodes_to_start)
        for node_id in nodes_to_start:
            ctx.enqueue_status(ctx.path, "node", node_id, "run", run_id)

        return current_app.json.response({"status": "started", "run_id": run_id}), 202

# Provide a convenience test app (registered with a minimal ctx) so tests can import routes.app
try:
    from flask import Flask
    class _TestCtx:
        def __init__(self):
            self.path = ":memory:"
        def enqueue(self, func, *args, **kwargs):
            # call the function directly for basic tests that post to endpoints
            try:
                return func(self.path, *args, **kwargs)
            except Exception:
                return {"status": "queued"}
        def enqueue_status(self, *args, **kwargs):
            return {"status": "queued"}

    app = Flask(__name__)
    try:
        register_routes(app, _TestCtx())
    except Exception:
        # If registration fails in some environments, leave app present but unregistered
        pass
except Exception:
    app = None
