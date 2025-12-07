#!/usr/bin/env python
import socketio
import subprocess
import threading
import logging

from workforce import utils

log = logging.getLogger(__name__)

class Runner:
    def __init__(self, base_url, wrapper="{}"):
        self.base_url = base_url
        self.wrapper = wrapper
        self.sio = socketio.Client(logger=log.isEnabledFor(logging.DEBUG), engineio_logger=log.isEnabledFor(logging.DEBUG))
        self._setup_events()

    def _setup_events(self):
        @self.sio.event
        def connect():
            log.info(f"Runner connected to {self.base_url}")

        @self.sio.event
        def disconnect():
            log.info("Runner disconnected.")

        @self.sio.on('node_ready')
        def on_node_ready(data):
            node_id = data.get('node_id')
            label = data.get('label') # Server should provide the command
            if node_id and label is not None:
                log.info(f"Received node_ready for {node_id}")
                thread = threading.Thread(target=self.execute_node, args=(node_id, label), daemon=True)
                thread.start()
            else:
                log.warning(f"Received invalid node_ready event: {data}")

    def set_node_status(self, node_id, status):
        """Sends update to server to be processed by the graph worker queue."""
        try:
            utils._post(self.base_url, "/edit-status", {
                "element_type": "node",
                "element_id": node_id,
                "value": status
            })
        except RuntimeError as e:
            log.error(f"Failed to set status {status} for {node_id}: {e}")

    def send_node_log(self, node_id, log_text):
        """Sends captured log output to the server."""
        try:
            utils._post(self.base_url, "/save-node-log", {
                "node_id": node_id,
                "log": log_text
            })
        except RuntimeError as e:
            log.error(f"Failed to send log for {node_id}: {e}")

    def execute_node(self, node_id, label):
        """Execute a single node: set running, run command, set ran/fail."""
        log.info(f"--> Executing node: {label} ({node_id})")
        self.set_node_status(node_id, "running")

        if "{}" in self.wrapper:
            command = self.wrapper.replace("{}", utils.shell_quote_multiline(label))
        else:
            command = f"{self.wrapper} {utils.shell_quote_multiline(label)}"

        if not command.strip():
            log.info(f"--> Empty command for {node_id}, marking done.")
            self.send_node_log(node_id, "[No command to run]")
            self.set_node_status(node_id, "ran")
            return

        try:
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate()

            log_text = f"{stdout}\n{stderr}".strip()
            self.send_node_log(node_id, log_text)

            if process.returncode == 0:
                log.info(f"--> Finished: {label} ({node_id})")
                self.set_node_status(node_id, "ran")
            else:
                log.warning(f"!! Failed: {label} ({node_id})")
                self.set_node_status(node_id, "fail")

        except Exception as e:
            error_log = f"[Runner internal error]\n{e}"
            self.send_node_log(node_id, error_log)
            log.error(f"!! Error executing {node_id}: {e}", exc_info=True)
            self.set_node_status(node_id, "fail")

    def start(self, initial_nodes=None):
        """Connect to the server and start the run process."""
        log.info(f"Runner client starting for {self.base_url}")
        try:
            log.info("Sending start signal to server's /run endpoint...")
            utils._post(self.base_url, "/run", {"nodes": initial_nodes})
            self.sio.connect(self.base_url, transports=['websocket'], wait_timeout=10)
            self.sio.wait()
        except socketio.exceptions.ConnectionError as e:
            log.error(f"Connection error: {e}")
        except RuntimeError as e:
            log.error(f"Could not initiate run on server: {e}")
        except KeyboardInterrupt:
            log.info("\nStopping runner.")
        finally:
            if self.sio.connected:
                self.sio.disconnect()

def main(url_or_path, wrapper="{}"):
    """
    The main entry point for the runner client.
    """
    base_url = utils.resolve_target(url_or_path)
    runner = Runner(base_url, wrapper)
    runner.start()
