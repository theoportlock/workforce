import threading
import logging
from workforce import edit
import networkx as nx

log = logging.getLogger(__name__)

def start_graph_worker(ctx):
    def _check_and_trigger_successors(path, G, completed_node_id):
        """
        After node completed, check successors and queue those whose predecessors are 'ran'.
        """
        if completed_node_id not in G:
            log.warning("Completed node %s not found in graph", completed_node_id)
            return
        for successor in G.successors(completed_node_id):
            predecessors = list(G.predecessors(successor))
            all_deps_met = all(G.nodes[p].get("status") == "ran" for p in predecessors)
            if all_deps_met:
                # Only schedule if not already run/run
                if G.nodes[successor].get("status") not in ("run", "running", "ran"):
                    ctx.enqueue_status(path, "node", successor, "run", ctx.active_node_run.get(completed_node_id))
            else:
                log.debug("Dependencies not met for %s", successor)

    def worker():
        log.info("Graph worker thread started.")
        while True:
            func, args, kwargs = ctx.mod_queue.get()
            try:
                func(*args, **kwargs)

                # Broadcast latest graph
                G = edit.load_graph(ctx.path)
                data = nx.node_link_data(G, link="links")
                data["graph"] = G.graph
                try:
                    ctx.socketio.emit("graph_update", data, namespace="/")
                except Exception:
                    log.exception("Failed to emit graph_update")

                # Lifecycle handling for status changes
                name = getattr(func, "__name__", "")
                if name in ("edit_status_in_graph",):
                    _, el_type, el_id, status = args
                    run_id = ctx.active_node_run.get(el_id)
                    if el_type == "node" and status == "run":
                        # decide execution: server-side or runner client
                        run_on_server = ctx.active_runs.get(run_id, {}).get("run_on_server", False)
                        if run_on_server:
                            label = G.nodes[el_id].get("label", "")
                            threading.Thread(target=__import__("workforce.server.execution", fromlist=["execute_node_on_server"]).execute_node_on_server, args=(ctx, el_id, label), daemon=True).start()
                        else:
                            try:
                                ctx.socketio.emit("node_ready", {"node_id": el_id, "label": G.nodes[el_id].get("label", ""), "run_id": run_id})
                            except Exception:
                                log.exception("Failed to emit node_ready")
                    elif el_type == "node" and status == "ran":
                        _check_and_trigger_successors(args[0], G, el_id)
                    elif el_type == "edge" and status == "ready":
                        # same logic as earlier: if all incoming edges ready -> clear them and run target
                        edge_end = None
                        for u, v, ed in G.edges(data=True):
                            if ed.get("id") == el_id:
                                edge_end = (u, v)
                                break
                        if edge_end:
                            _, v = edge_end
                            in_edges = list(G.in_edges(v, data=True))
                            all_ready = all(ed.get("status") == "ready" for _, _, ed in in_edges)
                            if all_ready:
                                # determine candidate run_id from predecessors
                                candidate_run_id = None
                                for uu, _, _ in in_edges:
                                    candidate_run_id = ctx.active_node_run.get(uu)
                                    if candidate_run_id:
                                        break
                                # clear incoming edges
                                for _, _, ed in in_edges:
                                    eid2 = ed.get("id")
                                    if eid2 and ed.get("status") != "":
                                        ctx.enqueue(edit.edit_status_in_graph, ctx.path, "edge", eid2, "")
                                # start target if not already
                                node_status = G.nodes[v].get("status", "")
                                if node_status not in ("run", "running", "ran"):
                                    ctx.enqueue_status(ctx.path, "node", v, "run", candidate_run_id)
            except Exception:
                log.exception("Graph worker error")
            finally:
                ctx.mod_queue.task_done()

                # run completion check (simple)
                if ctx.mod_queue.empty():
                    def _check_complete():
                        try:
                            G_local = edit.load_graph(ctx.path)
                        except Exception:
                            return
                        # check active runs
                        for run_id, meta in list(ctx.active_runs.items()):
                            nodes_set = set(meta.get("nodes", set()))
                            if not nodes_set:
                                try:
                                    ctx.socketio.emit("run_complete", {"run_id": run_id})
                                except Exception:
                                    log.exception("Failed to emit run_complete")
                                ctx.active_runs.pop(run_id, None)
                                for n, rid in list(ctx.active_node_run.items()):
                                    if rid == run_id:
                                        ctx.active_node_run.pop(n, None)
                                continue
                            still_running = any(G_local.nodes[n].get("status") in ("run", "running") for n in nodes_set if n in G_local.nodes)
                            if not still_running:
                                try:
                                    ctx.socketio.emit("run_complete", {"run_id": run_id})
                                except Exception:
                                    log.exception("Failed to emit run_complete")
                                ctx.active_runs.pop(run_id, None)
                                for n in list(nodes_set):
                                    ctx.active_node_run.pop(n, None)
                    try:
                        ctx.socketio.start_background_task(_check_complete)
                    except Exception:
                        # fallback to thread
                        threading.Thread(target=_check_complete, daemon=True).start()

    threading.Thread(target=worker, daemon=True).start()
