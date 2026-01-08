import threading
import logging
import requests
import socketio

from workforce import utils

log = logging.getLogger(__name__)

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
                    server_root = utils.WORKSPACE_SERVER_URL
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
            result = utils._post(self.base_url, "/client-disconnect", {})
            log.info(f"Client disconnected from {self.workspace_id}")
            return result
        except Exception as e:
            log.error(f"Error during client disconnect: {e}")
            return None

    def get_graph(self, timeout=1.0):
        r = requests.get(self._url("/get-graph"), timeout=timeout)
        r.raise_for_status()
        return r.json()

    # Convenience POST wrappers
    def add_node(self, label, x, y, status=""):
        return utils._post(self.base_url, "/add-node", {"label": label, "x": x, "y": y, "status": status})

    def remove_node(self, node_id):
        return utils._post(self.base_url, "/remove-node", {"node_id": node_id})

    def add_edge(self, source, target):
        return utils._post(self.base_url, "/add-edge", {"source": source, "target": target})

    def remove_edge(self, source, target):
        return utils._post(self.base_url, "/remove-edge", {"source": source, "target": target})

    def edit_status(self, element_type, element_id, value):
        return utils._post(self.base_url, "/edit-status", {"element_type": element_type, "element_id": element_id, "value": value})

    def edit_node_position(self, node_id, x, y):
        return utils._post(self.base_url, "/edit-node-position", {"node_id": node_id, "x": x, "y": y})

    def edit_wrapper(self, wrapper):
        return utils._post(self.base_url, "/edit-wrapper", {"wrapper": wrapper})

    def edit_node_label(self, node_id, label):
        return utils._post(self.base_url, "/edit-node-label", {"node_id": node_id, "label": label})

    def save_node_log(self, node_id, log_text):
        return utils._post(self.base_url, "/save-node-log", {"node_id": node_id, "log": log_text})

    def run(self, nodes=None):
        payload = {"nodes": nodes}
        return utils._post(self.base_url, "/run", payload)

    def save_as(self, new_path):
        """Save graph to new file and return new workspace info."""
        return utils._post(self.base_url, "/save-as", {"new_path": new_path})

    def client_connect(self):
        """Register client connection with the server."""
        try:
            return utils._post(self.base_url, "/client-connect", {"workfile_path": self.workfile_path})
        except Exception:
            return None

