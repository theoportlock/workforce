from dataclasses import dataclass, field
import queue
import os
import uuid
import json
from typing import Any, Callable, Dict

@dataclass
class ServerContext:
    path: str
    port: int
    server_cache_dir: str
    mod_queue: queue.Queue
    socketio: Any = None

    # per-run tracking
    active_runs: Dict[str, dict] = field(default_factory=dict)       # run_id -> {"nodes": set(), "subset_only": bool, "subset_nodes": set()}
    active_node_run: Dict[str, str] = field(default_factory=dict)    # node_id -> run_id

    def enqueue(self, func: Callable, *args, **kwargs):
        """
        Cache the mutation and push task onto the queue.
        """
        try:
            request_id = str(uuid.uuid4())
            request_file = os.path.join(self.server_cache_dir, f"{request_id}.json")
            payload = {"operation": getattr(func, "__name__", str(func)), "args": args, "kwargs": kwargs}
            with open(request_file, "w") as f:
                json.dump(payload, f)
        except Exception:
            pass
        self.mod_queue.put((func, args, kwargs))
        return {"status": "queued"}

    def enqueue_status(self, path: str, element_type: str, element_id: str, value: str, run_id: str | None = None):
        """
        Record run mapping and enqueue the status edit.
        """
        if run_id and element_type == "node":
            # Ensure run exists before adding nodes
            self.active_runs.setdefault(run_id, {"nodes": set()})
            
            if value == "run":
                self.active_node_run[element_id] = run_id
                self.active_runs[run_id]["nodes"].add(element_id)
            elif value in ("running", "ran", "fail"):
                # Ensure mapping exists if not already set
                if element_id not in self.active_node_run and run_id:
                    self.active_node_run[element_id] = run_id
                    self.active_runs[run_id]["nodes"].add(element_id)
        return self.enqueue(__import__("workforce.edit", fromlist=["edit_status_in_graph"]).edit_status_in_graph, path, element_type, element_id, value)
