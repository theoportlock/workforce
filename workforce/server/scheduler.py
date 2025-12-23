import logging
from workforce import edit
from workforce.server.context import ServerContext

log = logging.getLogger(__name__)

def determine_start_nodes(G, selected_nodes, subset_only, start_failed=False):
	"""
	Compute initial nodes to start for a run.
	"""
	if subset_only and selected_nodes:
		subgraph = G.subgraph(selected_nodes).copy()
	else:
		subgraph = G

	if not subset_only and selected_nodes:
		return list(selected_nodes)

	roots = [n for n, d in subgraph.in_degree() if d == 0]
	if start_failed and not selected_nodes:
		failed = [n for n, d in G.nodes(data=True) if d.get("status") == "fail"]
		return failed or roots
	return roots

# Lifecycle handlers
def handle_node_run(ctx: ServerContext, G, node_id, run_id):
	# Map node->run and enqueue node_ready emit
	if run_id:
		ctx.active_node_run[node_id] = run_id
		ctx.active_runs.setdefault(run_id, {"nodes": set()})["nodes"].add(node_id)

	# Notify runner clients
	ctx.socketio.emit("node_ready", {"node_id": node_id, "label": G.nodes[node_id].get("label",""), "run_id": run_id})

def handle_node_ran(ctx: ServerContext, G, node_id, run_id):
	# mark outgoing edges ready for this run
	run_meta = ctx.active_runs.get(run_id, {})
	subset_only = run_meta.get("subset_only", False)
	subset_nodes = run_meta.get("subset_nodes", set())
	
	for _, tgt, edata in G.out_edges(node_id, data=True):
		# if subset_only, only mark edges ready if target is in subset
		if subset_only and tgt not in subset_nodes:
			continue
		eid = edata.get("id")
		if eid and edata.get("status") != "ready":
			# enqueue an edge status change that keeps run_id
			ctx.enqueue(__import__("workforce.edit", fromlist=["edit_status_in_graph"]).edit_status_in_graph, ctx.path, "edge", eid, "ready")

	# cleanup mapping for this node
	if run_id:
		ctx.active_runs.get(run_id, {"nodes": set()})["nodes"].discard(node_id)
		ctx.active_node_run.pop(node_id, None)

def handle_edge_ready(ctx: ServerContext, G, edge_id, run_id):
	# find edge endpoints
	edge_end = None
	for u, v, ed in G.edges(data=True):
		if ed.get("id") == edge_id:
			edge_end = (u, v)
			break
	if not edge_end:
		return
	_, v = edge_end
	in_edges = list(G.in_edges(v, data=True))
	all_ready = all(ed.get("status") == "ready" for _, _, ed in in_edges)
	if not all_ready:
		return

	# choose run_id from predecessors if not supplied
	candidate_run_id = run_id
	if not candidate_run_id:
		for uu, _, _ in in_edges:
			r = ctx.active_node_run.get(uu)
			if r:
				candidate_run_id = r
				break

	# clear incoming edges statuses
	for _, _, ed in in_edges:
		eid2 = ed.get("id")
		if eid2 and ed.get("status") != "":
			ctx.enqueue(edit.edit_status_in_graph, ctx.path, "edge", eid2, "")

	# start node if not already running/ran
	node_status = G.nodes[v].get("status", "")
	if node_status not in ("run", "running", "ran"):
		ctx.enqueue(edit.edit_status_in_graph, ctx.path, "node", v, "run")


STATUS_HANDLERS = {
	("node", "run"): handle_node_run,
	("node", "ran"): handle_node_ran,
	("edge", "ready"): handle_edge_ready,
}

def maybe_emit_run_complete(ctx: ServerContext):
	# Called after each worker task to check active runs
	try:
		G = edit.load_graph(ctx.path)
	except Exception:
		return
	for run_id, meta in list(ctx.active_runs.items()):
		nodes_set = set(meta.get("nodes", set()))
		if not nodes_set:
			ctx.socketio.emit("run_complete", {"run_id": run_id})
			ctx.active_runs.pop(run_id, None)
			# cleanup node mapping
			for n, rid in list(ctx.active_node_run.items()):
				if rid == run_id:
					ctx.active_node_run.pop(n, None)
			continue
		# check if any nodes are still running
		still_running = any(G.nodes[n].get("status") in ("run", "running") for n in nodes_set if n in G.nodes)
		if not still_running:
			ctx.socketio.emit("run_complete", {"run_id": run_id})
			ctx.active_runs.pop(run_id, None)
			for n in list(nodes_set):
				ctx.active_node_run.pop(n, None)
