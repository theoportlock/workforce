import logging
import threading
import uuid

import requests
import socketio

from workforce import utils

log = logging.getLogger(__name__)


class OperationQueue:
    """Queues operations for batching and provides optimistic updates.
    
    Operation lifecycle:
    - queued: Added to queue, waiting for batch send
    - pending: Sent to server, waiting for confirmation
    - confirmed: Server confirmed the operation
    - superseded: Server sent update that replaces this operation
    """
    
    def __init__(self, batch_interval_ms: int = 100, max_queue_size: int = 1000):
        self.queue: list[dict] = []
        self.pending: dict[str, dict] = {}
        self.batch_interval_ms = batch_interval_ms
        self.max_queue_size = max_queue_size
        self._batch_timer: threading.Timer | None = None
        self._flush_callback: callable | None = None
    
    def set_flush_callback(self, callback: callable):
        """Set callback for flushing operations to server."""
        self._flush_callback = callback
    
    def enqueue(self, op_type: str, data: dict) -> str:
        """Add operation to queue for batch sending, return operation ID."""
        if len(self.queue) >= self.max_queue_size:
            log.warning(f"Queue full ({self.max_queue_size}), dropping operation")
            return None
        
        op_id = str(uuid.uuid4())
        op = {"id": op_id, "type": op_type, "data": data, "status": "queued"}
        self.queue.append(op)
        
        self._reset_batch_timer()
        
        return op_id
    
    def enqueue_position(self, node_id: str, x: float, y: float) -> str:
        """Convenience method for position updates."""
        return self.enqueue("position", {"node_id": node_id, "x": x, "y": y})
    
    def enqueue_add_node(self, node_id: str, label: str, x: float, y: float, status: str = "") -> str:
        """Convenience method for adding a node."""
        return self.enqueue("add_node", {"node_id": node_id, "label": label, "x": x, "y": y, "status": status})
    
    def enqueue_remove_node(self, node_id: str) -> str:
        """Convenience method for removing a node."""
        return self.enqueue("remove_node", {"node_id": node_id})
    
    def enqueue_status(self, element_type: str, element_id: str, value: str) -> str:
        """Convenience method for status updates."""
        return self.enqueue("status", {"element_type": element_type, "element_id": element_id, "value": value})
    
    def enqueue_label(self, node_id: str, label: str) -> str:
        """Convenience method for label updates."""
        return self.enqueue("label", {"node_id": node_id, "label": label})
    
    def enqueue_edge(self, source: str, target: str, edge_type: str = "blocking") -> str:
        """Convenience method for adding edges."""
        return self.enqueue("edge", {"source": source, "target": target, "edge_type": edge_type})
    
    def enqueue_remove_edge(self, source: str, target: str) -> str:
        """Convenience method for removing edges."""
        return self.enqueue("remove_edge", {"source": source, "target": target})
    
    def _reset_batch_timer(self):
        """Reset the batch flush timer."""
        if self._batch_timer:
            self._batch_timer.cancel()
        self._batch_timer = threading.Timer(
            self.batch_interval_ms / 1000.0,
            self._do_flush
        )
        self._batch_timer.daemon = True
        self._batch_timer.start()
    
    def _do_flush(self):
        """Internal flush handler."""
        if self._flush_callback:
            self._flush_callback()
    
    def flush(self):
        """Send batched operations to server. Called externally (e.g., before run)."""
        self._do_flush()
    
    def get_pending_count(self) -> int:
        """Return count of operations waiting to be sent or confirmed."""
        return len(self.queue) + len(self.pending)
    
    def confirm_operation(self, op_id: str):
        """Mark operation as confirmed by server."""
        self.pending.pop(op_id, None)
    
    def confirm_operations(self, op_ids: list[str]):
        """Mark multiple operations as confirmed."""
        for op_id in op_ids:
            self.pending.pop(op_id, None)
    
    def mark_superseded(self, op_ids: list[str]):
        """Mark operations as superseded by server update."""
        for op_id in op_ids:
            self.pending.pop(op_id, None)
    
    def get_queue_snapshot(self) -> list[dict]:
        """Get copy of current queue for debugging."""
        return list(self.queue)
    
    def clear(self):
        """Clear all queued and pending operations."""
        if self._batch_timer:
            self._batch_timer.cancel()
        self.queue.clear()
        self.pending.clear()

class ServerClient:
    def __init__(self, base_url: str, workspace_id: str, workfile_path: str, on_graph_update=None):
        """
        Initialize server client for a workspace.
        
        Args:
            base_url: Base server URL (e.g., http://127.0.0.1:5042/workspace/<ws_id>)
            workspace_id: Workspace ID (e.g., ws_abc123)
            workfile_path: Absolute path to workfile (for client_connect)
            on_graph_update: Callback for graph updates
        """
        self.base_url = base_url.rstrip("/")
        self.workspace_id = workspace_id
        self.workfile_path = workfile_path
        self.workspace_room = f"ws:{workspace_id}"
        self.on_graph_update = on_graph_update
        self.sio = None
        self.connected = False
        self.client_id: str | None = None
        self.socketio_sid: str | None = None
        
        self.op_queue = OperationQueue()
        self.op_queue.set_flush_callback(self._flush_queue)

    def _flush_queue(self):
        """Flush queued operations to server in batches."""
        if not self.op_queue.queue:
            return
        
        queue_snapshot = list(self.op_queue.queue)
        self.op_queue.pending.update({op["id"]: op for op in queue_snapshot})
        self.op_queue.queue.clear()
        
        position_ops = [op for op in queue_snapshot if op["type"] == "position"]
        status_ops = [op for op in queue_snapshot if op["type"] == "status"]
        label_ops = [op for op in queue_snapshot if op["type"] == "label"]
        add_node_ops = [op for op in queue_snapshot if op["type"] == "add_node"]
        remove_node_ops = [op for op in queue_snapshot if op["type"] == "remove_node"]
        add_edge_ops = [op for op in queue_snapshot if op["type"] == "edge"]
        remove_edge_ops = [op for op in queue_snapshot if op["type"] == "remove_edge"]
        
        confirmed_ids = []
        
        if position_ops:
            try:
                positions = [{"node_id": op["data"]["node_id"], "x": op["data"]["x"], "y": op["data"]["y"]} for op in position_ops]
                utils._post(self.base_url, "/edit-node-positions", {"positions": positions})
                confirmed_ids.extend([op["id"] for op in position_ops])
            except Exception as e:
                log.error(f"Failed to batch send positions: {e}")
        
        if status_ops:
            try:
                updates = [{"element_type": op["data"]["element_type"], "element_id": op["data"]["element_id"], "value": op["data"]["value"]} for op in status_ops]
                utils._post(self.base_url, "/edit-statuses", {"updates": updates})
                confirmed_ids.extend([op["id"] for op in status_ops])
            except Exception as e:
                log.error(f"Failed to batch send statuses: {e}")
        
        if label_ops:
            for op in label_ops:
                try:
                    utils._post(self.base_url, "/edit-node-label", {"node_id": op["data"]["node_id"], "label": op["data"]["label"]})
                    confirmed_ids.append(op["id"])
                except Exception as e:
                    log.error(f"Failed to update label: {e}")
        
        for op in add_node_ops:
            try:
                utils._post(self.base_url, "/add-node", {"label": op["data"]["label"], "x": op["data"]["x"], "y": op["data"]["y"], "status": op["data"]["status"]})
                confirmed_ids.append(op["id"])
            except Exception as e:
                log.error(f"Failed to add node: {e}")
        
        for op in remove_node_ops:
            try:
                utils._post(self.base_url, "/remove-node", {"node_id": op["data"]["node_id"]})
                confirmed_ids.append(op["id"])
            except Exception as e:
                log.error(f"Failed to remove node: {e}")
        
        for op in add_edge_ops:
            try:
                utils._post(self.base_url, "/add-edge", {"source": op["data"]["source"], "target": op["data"]["target"], "edge_type": op["data"]["edge_type"]})
                confirmed_ids.append(op["id"])
            except Exception as e:
                log.error(f"Failed to add edge: {e}")
        
        for op in remove_edge_ops:
            try:
                utils._post(self.base_url, "/remove-edge", {"source": op["data"]["source"], "target": op["data"]["target"]})
                confirmed_ids.append(op["id"])
            except Exception as e:
                log.error(f"Failed to remove edge: {e}")
        
        self.op_queue.confirm_operations(confirmed_ids)

    def flush(self):
        """Public method to flush queue before critical operations."""
        self._flush_queue()

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return self.base_url + path

    def connect(self):
        if self.sio is not None:
            return

        def connect_worker():
            try:
                self.sio = socketio.Client(logger=False, engineio_logger=False)

                @self.sio.event
                def connect():
                    log.info("Successfully connected to %s", self.base_url)
                    self.connected = True
                    self.socketio_sid = getattr(self.sio, "sid", None)
                    
                    # Join workspace room immediately after connect
                    try:
                        self.sio.emit('join_room', {"room": self.workspace_room})
                        log.info(f"Joined workspace room {self.workspace_room}")
                    except Exception as e:
                        log.warning(f"Failed to join workspace room: {e}")

                @self.sio.event
                def connect_error(data):
                    log.warning("SocketIO connection failed: %s", data)

                @self.sio.event
                def disconnect():
                    log.info("SocketIO disconnected")
                    self.connected = False
                    self.socketio_sid = None

                @self.sio.on('graph_update')
                def _on_graph_update(data):
                    log.debug(f"Received graph_update event: {data.get('nodes', []).__len__()} nodes")
                    if callable(self.on_graph_update):
                        self.on_graph_update(data)

                @self.sio.on('status_change')
                def _on_status_change(data):
                    log.debug(f"Received status_change event: node_id={data.get('node_id')}, status={data.get('status')}")
                    if callable(self.on_graph_update):
                        self.on_graph_update(data)

                # Connect to the server root derived from the workspace base_url
                try:
                    from urllib.parse import urlsplit
                    split = urlsplit(self.base_url)
                    server_root = f"{split.scheme}://{split.netloc}"
                except Exception:
                    # Fallback to server discovery if URL parsing fails
                    server_root = utils.resolve_server()
                self.sio.connect(server_root, wait_timeout=5, auth=None)
            except Exception as e:
                log.warning("SocketIO setup failed: %s", e)
                self.sio = None

        t = threading.Thread(target=connect_worker, daemon=True)
        t.start()

    def disconnect(self):
        """Disconnect SocketIO client."""
        if self.sio and getattr(self.sio, "connected", False):
            try:
                self.sio.disconnect()
                log.info("SocketIO disconnected")
            except Exception as e:
                log.warning("Error disconnecting SocketIO: %s", e)
            self.sio = None
        self.connected = False

    def client_disconnect(self):
        """Unregister client disconnection. May trigger workspace context destruction."""
        try:
            # First disconnect SocketIO
            self.disconnect()
            # Then notify server via REST
            payload = {
                "client_type": "gui",
                "client_id": self.client_id,
            }
            result = utils._post(self.base_url, "/client-disconnect", payload)
            log.info(f"Client disconnected from {self.workspace_id}")
            return result
        except Exception as e:
            log.error(f"Error during client disconnect: {e}")
            return None

    def get_graph(self, timeout=1.0):
        r = requests.get(self._url("/get-graph"), timeout=timeout)
        r.raise_for_status()
        return r.json()

    def get_clients(self, timeout=2.0):
        r = requests.get(self._url("/clients"), timeout=timeout)
        r.raise_for_status()
        return r.json()

    def get_runs(self, timeout=2.0):
        r = requests.get(self._url("/runs"), timeout=timeout)
        r.raise_for_status()
        return r.json()

    # Convenience POST wrappers (queued for batching)
    def add_node(self, label, x, y, status=""):
        """Add node - queues operation for batching."""
        import uuid
        node_id = str(uuid.uuid4())
        self.op_queue.enqueue_add_node(node_id, label, x, y, status)
        return {"node_id": node_id, "label": label, "x": x, "y": y, "status": status}

    def remove_node(self, node_id):
        """Remove node - queues operation for batching."""
        self.op_queue.enqueue_remove_node(node_id)
        return {"node_id": node_id}

    def add_edge(self, source, target, edge_type="blocking"):
        """Add edge - queues operation for batching."""
        self.op_queue.enqueue_edge(source, target, edge_type)
        return {"source": source, "target": target}

    def remove_edge(self, source, target):
        """Remove edge - queues operation for batching."""
        self.op_queue.enqueue_remove_edge(source, target)
        return {"source": source, "target": target}

    def edit_edge_type(self, source, target, edge_type="blocking"):
        return utils._post(self.base_url, "/edit-edge-type", {"source": source, "target": target, "edge_type": edge_type})

    def edit_status(self, element_type, element_id, value):
        """Edit status - queues operation for batching."""
        self.op_queue.enqueue_status(element_type, element_id, value)
        return {"element_type": element_type, "element_id": element_id, "value": value}

    def edit_node_position(self, node_id, x, y):
        """Edit node position - queues operation for batching."""
        self.op_queue.enqueue_position(node_id, x, y)
        return {"node_id": node_id, "x": x, "y": y}

    def edit_node_positions(self, positions):
        """Batch update positions for multiple nodes - queues all for batching.
        
        Args:
            positions: List of dicts with keys: node_id, x, y
        """
        for pos in positions:
            self.op_queue.enqueue_position(pos["node_id"], pos.get("x", 0), pos.get("y", 0))
        return {"positions": positions}

    def edit_statuses(self, updates):
        """Batch update statuses for multiple elements - queues all for batching.
        
        Args:
            updates: List of dicts with keys: element_type, element_id, value
        """
        for upd in updates:
            self.op_queue.enqueue_status(upd["element_type"], upd["element_id"], upd["value"])
        return {"updates": updates}

    def remove_node_logs(self, node_ids):
        """Remove execution logs from multiple nodes.
        
        Args:
            node_ids: List of node IDs to clear logs from
        """
        return utils._post(self.base_url, "/remove-node-logs", {"node_ids": node_ids})

    def edit_wrapper(self, wrapper):
        return utils._post(self.base_url, "/edit-wrapper", {"wrapper": wrapper})

    def edit_node_label(self, node_id, label):
        """Edit node label - queues operation for batching."""
        self.op_queue.enqueue_label(node_id, label)
        return {"node_id": node_id, "label": label}

    def save_node_log(self, node_id, log_text):
        return utils._post(self.base_url, "/save-node-log", {"node_id": node_id, "log": log_text})

    def run(self, nodes=None):
        """Run workflow - flushes queue first, then sends run request."""
        self.flush()
        payload = {"nodes": nodes}
        return utils._post(self.base_url, "/run", payload)

    def save_as(self, new_path):
        """Save graph to new file and return new workspace info."""
        return utils._post(self.base_url, "/save-as", {"new_path": new_path})

    def client_connect(self):
        """Register client connection with the server."""
        try:
            payload = {
                "workfile_path": self.workfile_path,
                "client_type": "gui",
                "socketio_sid": self.socketio_sid,
            }
            resp = utils._post(self.base_url, "/client-connect", payload)
            self.client_id = resp.get("client_id") if isinstance(resp, dict) else None
            return resp
        except Exception:
            return None

