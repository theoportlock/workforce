import threading
import logging
from workforce import edit
import networkx as nx

log = logging.getLogger(__name__)

def start_graph_worker(ctx):
    def _mark_outgoing_edges_ready(workfile_path, G, completed_node_id, run_id):
        """
        When a node completes (ran), set all outgoing edges to 'to_run' status.
        Only propagates to nodes that are part of the run (if subset run).
        """
        if completed_node_id not in G:
            log.warning("Completed node %s not found in graph", completed_node_id)
            return
        
        out_edges = list(G.out_edges(completed_node_id, data=True))
        log.info(f"Node {completed_node_id} completed, checking {len(out_edges)} outgoing edges")
        
        # Get the run metadata
        run_metadata = ctx.active_runs.get(run_id, {})
        run_nodes = run_metadata.get("nodes", set())
        subset_only = run_metadata.get("subset_only", False)
        
        # First pass: ensure all edges have IDs
        needs_save = False
        for u, v, edge_data in out_edges:
            if not edge_data.get("id"):
                import uuid
                edge_id = str(uuid.uuid4())
                G[u][v]["id"] = edge_id
                log.info(f"Assigned ID {edge_id} to edge {u}->{v}")
                needs_save = True
        
        # Save once if any edges needed IDs
        if needs_save:
            edit.save_graph(G, workfile_path)
        
        # Second pass: mark edges as to_run
        for u, v, edge_data in out_edges:
            # Only propagate if target is in the subset run (if this is a subset run)
            if subset_only and v not in run_nodes:
                log.info(f"Skipping edge to {v} - not in subset run")
                continue
            
            edge_id = edge_data["id"]  # Should exist now
            log.info(f"Setting edge {edge_id} ({u}->{v}) to to_run")
            ctx.enqueue_status(workfile_path, "edge", edge_id, "to_run", run_id)

    def _check_target_node_ready(workfile_path, G, edge_id, run_id):
        """
        When an edge becomes 'to_run', check if target node's ALL incoming edges are 'to_run'.
        If yes, clear those edges and set target node to 'run'.
        """
        # Find the edge by id
        target_node = None
        source_node = None
        for u, v, ed in G.edges(data=True):
            if ed.get("id") == edge_id:
                source_node = u
                target_node = v
                break
        
        if not target_node:
            log.warning(f"Could not find target node for edge {edge_id}")
            return
        
        # Determine run_id from the source node if not provided
        if not run_id:
            run_id = ctx.active_node_run.get(source_node)
        
        # Get the run metadata
        run_metadata = ctx.active_runs.get(run_id, {})
        run_nodes = run_metadata.get("nodes", set())
        subset_only = run_metadata.get("subset_only", False)
        
        # If this is a subset run and target is not in it, don't queue it
        if subset_only and target_node not in run_nodes:
            log.info(f"Target node {target_node} not in subset run, skipping")
            return
        
        # Get all incoming edges to target
        in_edges = list(G.in_edges(target_node, data=True))
        log.info(f"Checking target node {target_node}: {len(in_edges)} incoming edges")
        
        # Check if all incoming edges are 'to_run'
        all_ready = all(ed.get("status") == "to_run" for _, _, ed in in_edges)
        
        if all_ready:
            log.info(f"All dependencies met for node {target_node}, clearing edges and queuing node")
            
            # Clear all incoming edge statuses
            for _, _, ed in in_edges:
                eid = ed.get("id")
                if eid:
                    ctx.enqueue(edit.edit_status_in_graph, workfile_path, "edge", eid, "")
            
            # Set target node to 'run' (only if not already running/ran)
            current_status = G.nodes[target_node].get("status", "")
            if current_status not in ("run", "running", "ran"):
                log.info(f"Queuing node {target_node} for execution with run_id={run_id}")
                ctx.enqueue_status(workfile_path, "node", target_node, "run", run_id)
            else:
                log.debug(f"Node {target_node} already has status {current_status}, not queuing")
        else:
            ready_count = sum(1 for _, _, ed in in_edges if ed.get("status") == "to_run")
            log.info(f"Node {target_node} not ready: {ready_count}/{len(in_edges)} edges ready")

    def worker():
        log.info(f"Graph worker thread started for workspace {ctx.workspace_id}.")
        while True:
            item = ctx.mod_queue.get()
            
            # None signals shutdown
            if item is None:
                log.info(f"Graph worker shutting down for workspace {ctx.workspace_id}.")
                break
            
            func, args, kwargs = item
            try:
                func(*args, **kwargs)

                # Broadcast latest graph
                G = edit.load_graph(ctx.workfile_path)
                data = nx.node_link_data(G, edges="links")
                data["graph"] = G.graph
                
                # Emit domain event
                from workforce.server.events import Event
                log.info(f"Emitting GRAPH_UPDATED event for workspace {ctx.workspace_id} with {len(data.get('nodes', []))} nodes")
                ctx.events.emit(Event(type="GRAPH_UPDATED", payload=data))

                # Lifecycle handling for status changes
                name = getattr(func, "__name__", "")
                if name in ("edit_status_in_graph",):
                    _, el_type, el_id, status = args
                    
                    if el_type == "node":
                        run_id = ctx.active_node_run.get(el_id)
                        
                        if status == "run":
                            # Node is ready to execute - emit to runner clients
                            try:
                                label = G.nodes[el_id].get("label", "")
                                log.info(f"Emitting node_ready for {el_id} (run_id={run_id})")
                                
                                # Emit domain event
                                from workforce.server.events import Event
                                ctx.events.emit(Event(type="NODE_READY", payload={"node_id": el_id, "label": label, "run_id": run_id}))
                            except Exception:
                                log.exception("Failed to emit NODE_READY event")
                        
                        # Emit status_change for GUI updates
                        if status in ("ran", "fail", "running"):
                            try:
                                log.debug(f"Emitting status_change: node_id={el_id}, status={status}")
                                
                                # Emit domain event
                                from workforce.server.events import Event
                                event_type = {
                                    "running": "NODE_STARTED",
                                    "ran": "NODE_FINISHED",
                                    "fail": "NODE_FAILED"
                                }[status]
                                ctx.events.emit(Event(type=event_type, payload={"node_id": el_id, "status": status, "run_id": run_id}))
                            except Exception:
                                log.exception("Failed to emit node status event")
                        
                        # When node completes, mark outgoing edges as to_run
                        if status == "ran":
                            log.info(f"Node {el_id} completed successfully, propagating to successors")
                            _mark_outgoing_edges_ready(ctx.workfile_path, G, el_id, run_id)
                    
                    elif el_type == "edge":
                        if status == "to_run":
                            log.info(f"Edge {el_id} marked as to_run, checking target node")
                            # Get run_id from edge run mapping
                            run_id = getattr(ctx, "_edge_run_map", {}).get(el_id)
                            if not run_id:
                                # Fallback: try to find from source node
                                for u, v, ed in G.edges(data=True):
                                    if ed.get("id") == el_id:
                                        run_id = ctx.active_node_run.get(u)
                                        break
                            log.info(f"Edge {el_id} has run_id={run_id}")
                            _check_target_node_ready(ctx.workfile_path, G, el_id, run_id)
                        
            except Exception:
                log.exception("Graph worker error")
            finally:
                ctx.mod_queue.task_done()

                # Run completion check
                if ctx.mod_queue.empty():
                    def _check_complete():
                        try:
                            G_local = edit.load_graph(ctx.workfile_path)
                        except Exception:
                            return
                        
                        for run_id, meta in list(ctx.active_runs.items()):
                            nodes_set = set(meta.get("nodes", set()))
                            # Don't mark complete if nodes haven't been tracked yet (empty set during init)
                            if not nodes_set:
                                # Check if any node with 'run' status has this run_id
                                has_running_nodes = any(
                                    n for n, rid in ctx.active_node_run.items()
                                    if rid == run_id and G_local.nodes.get(n, {}).get("status") in ("run", "running")
                                )
                                if not has_running_nodes:
                                    try:
                                        log.info(f"Run {run_id} has no nodes and no running nodes, marking complete")
                                        
                                        # Emit domain event
                                        from workforce.server.events import Event
                                        ctx.events.emit(Event(type="RUN_COMPLETE", payload={"run_id": run_id}))
                                    except Exception:
                                        log.exception("Failed to emit RUN_COMPLETE event")
                                    ctx.active_runs.pop(run_id, None)
                                    for n, rid in list(ctx.active_node_run.items()):
                                        if rid == run_id:
                                            ctx.active_node_run.pop(n, None)
                                continue
                            
                            # Check if any nodes are still running
                            still_running = any(
                                G_local.nodes[n].get("status") in ("run", "running") 
                                for n in nodes_set if n in G_local.nodes
                            )
                            
                            if not still_running:
                                log.info(f"Run {run_id} complete (no nodes still running)")
                                try:
                                    # Emit domain event
                                    from workforce.server.events import Event
                                    ctx.events.emit(Event(type="RUN_COMPLETE", payload={"run_id": run_id}))
                                except Exception:
                                    log.exception("Failed to emit RUN_COMPLETE event")
                                ctx.active_runs.pop(run_id, None)
                                for n in list(nodes_set):
                                    ctx.active_node_run.pop(n, None)
                    
                    # Run completion check in background thread
                    threading.Thread(target=_check_complete, daemon=True).start()

    # Create and start the worker thread
    worker_thread = threading.Thread(target=worker, daemon=True)
    worker_thread.start()
    ctx.worker_thread = worker_thread
    log.info(f"Started graph worker thread for workspace {ctx.workspace_id}")
