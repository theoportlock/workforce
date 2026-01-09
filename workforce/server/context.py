from dataclasses import dataclass, field
import queue
import os
import uuid
import json
import threading
import time
import logging
from typing import Any, Callable, Dict
from pathlib import Path
from collections import deque

log = logging.getLogger(__name__)

@dataclass
class ServerContext:
    """
    Workspace-specific server context. Exists only while clients are connected.
    """
    workspace_id: str
    workfile_path: str
    server_cache_dir: str
    mod_queue: queue.Queue
    socketio: Any = None
    events: Any = None  # EventBus, set in __post_init__
    
    # Lifecycle tracking
    client_count: int = 0
    created_at: float = field(default_factory=time.time)
    worker_thread: threading.Thread | None = None
    
    # per-run tracking
    active_runs: Dict[str, dict] = field(default_factory=dict)       # run_id -> {"nodes": set(), "subset_only": bool}
    active_node_run: Dict[str, str] = field(default_factory=dict)    # node_id -> run_id
    
    # Request deduplication (idempotency)
    processed_requests: deque = field(default_factory=lambda: deque(maxlen=1000))  # Track last 1000 request IDs
    request_lock: threading.Lock = field(default_factory=threading.Lock)  # Protect processed_requests
    
    def __post_init__(self):
        """Initialize event bus with file logging."""
        from workforce.server.events import EventBus
        
        # Set up event log in ~/.workforce/events.log
        event_log_dir = Path.home() / ".workforce"
        event_log_path = event_log_dir / "events.log"
        
        self.events = EventBus(log_file=str(event_log_path))

    def increment_clients(self):
        """Called when a client connects."""
        self.client_count += 1

    def decrement_clients(self) -> int:
        """Called when a client disconnects. Returns new client count.
        
        Raises:
            ValueError: If client count would go negative (indicates double-disconnect bug)
        """
        if self.client_count <= 0:
            log.warning(f"Client count underflow detected for workspace {self.workspace_id}: "
                       f"decrement called when count is {self.client_count}. "
                       f"This indicates a double-disconnect bug.")
            # Don't raise exception to avoid breaking client, but log loudly
            return 0
        
        self.client_count -= 1
        return self.client_count

    def should_destroy(self) -> bool:
        """Returns True if context should be destroyed (no clients left)."""
        return self.client_count <= 0

    def enqueue(self, func: Callable, *args, idempotency_key: str | None = None, **kwargs):
        """
        Cache the mutation and push task onto the queue.
        
        Args:
            func: Function to execute
            *args: Positional arguments for func
            idempotency_key: Optional key to prevent duplicate operations
            **kwargs: Keyword arguments for func
        
        Returns:
            dict: Status dict with 'status' and optionally 'idempotency_key'
        """
        # Check for duplicate requests
        if idempotency_key:
            with self.request_lock:
                if idempotency_key in self.processed_requests:
                    log.info(f"Skipping duplicate request {idempotency_key}")
                    return {"status": "duplicate", "idempotency_key": idempotency_key}
                # Mark as processed before enqueuing to prevent race
                self.processed_requests.append(idempotency_key)
        
        # Cache request to disk for crash recovery
        try:
            request_id = idempotency_key or str(uuid.uuid4())
            request_file = os.path.join(self.server_cache_dir, f"{request_id}.json")
            payload = {
                "operation": getattr(func, "__name__", str(func)),
                "args": args,
                "kwargs": kwargs,
                "idempotency_key": idempotency_key
            }
            with open(request_file, "w") as f:
                json.dump(payload, f)
        except Exception as e:
            log.warning(f"Failed to cache request: {e}")
        
        # Queue the operation
        self.mod_queue.put((func, args, kwargs))
        return {"status": "queued", "idempotency_key": idempotency_key}

    def enqueue_status(self, workfile_path: str, element_type: str, element_id: str, value: str, run_id: str | None = None):
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
        elif run_id and element_type == "edge":
            # For edges, store run_id mapping so we can retrieve it later
            # We'll use a dictionary keyed by edge_id
            if not hasattr(self, "_edge_run_map"):
                self._edge_run_map = {}
            self._edge_run_map[element_id] = run_id
        return self.enqueue(__import__("workforce.edit", fromlist=["edit_status_in_graph"]).edit_status_in_graph, workfile_path, element_type, element_id, value)
