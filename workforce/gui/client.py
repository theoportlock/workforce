import threading
import logging
import requests
import socketio

from workforce import utils

log = logging.getLogger(__name__)

class ServerClient:
    def __init__(self, base_url: str, on_graph_update=None):
        self.base_url = base_url.rstrip("/")
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

                @self.sio.event
                def connect_error(data):
                    log.warning("SocketIO connection failed: %s", data)

                @self.sio.event
                def disconnect():
                    log.info("SocketIO disconnected")
                    self.connected = False

                @self.sio.on('graph_update')
                def _on_graph_update(data):
                    if callable(self.on_graph_update):
                        self.on_graph_update(data)

                self.sio.connect(self.base_url, wait_timeout=5, auth=None)
            except Exception as e:
                log.warning("SocketIO setup failed: %s", e)
                self.sio = None

        t = threading.Thread(target=connect_worker, daemon=True)
        t.start()

    def disconnect(self):
        if self.sio and getattr(self.sio, "connected", False):
            try:
                self.sio.disconnect()
            except Exception:
                pass
            self.sio = None

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

    def run(self, nodes=None, subset_only=False, run_on_server=False, start_failed=False):
        payload = {"nodes": nodes, "subset_only": subset_only, "run_on_server": run_on_server, "start_failed": start_failed}
        return utils._post(self.base_url, "/run", payload)

    def client_connect(self):
        try:
            return utils._post(self.base_url, "/client-connect")
        except Exception:
            return None

    def client_disconnect(self):
        try:
            return utils._post(self.base_url, "/client-disconnect")
        except Exception:
            return None
