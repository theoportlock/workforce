import socketio
import subprocess
import threading
import logging

from workforce import utils

log = logging.getLogger(__name__)

class Runner:
	def __init__(self, base_url: str, workspace_id: str, workfile_path: str, wrapper: str = "{}"):
		self.base_url = base_url
		self.workspace_id = workspace_id
		self.workfile_path = workfile_path
		self.workspace_room = f"ws:{workspace_id}"
		self.wrapper = wrapper
		self.run_id = None
		self.sio = socketio.Client(logger=log.isEnabledFor(logging.DEBUG), engineio_logger=log.isEnabledFor(logging.DEBUG))
		self._registered_with_server = False  # Track if we've registered with server
		self._setup_events()

	def _setup_events(self):
		@self.sio.event
		def connect():
			log.info(f"Runner connected to {self.base_url}")
			# Join workspace room for event isolation
			self.sio.emit('join_room', {'room': self.workspace_room})

		@self.sio.event
		def disconnect():
			log.info("Runner disconnected.")

		@self.sio.on('run_complete')
		def on_run_complete(data=None):
			run_id = None
			if isinstance(data, dict):
				run_id = data.get("run_id")
			if run_id and self.run_id and run_id != self.run_id:
				log.debug("Ignoring run_complete for other run_id %s", run_id)
				return
			log.info("Server signaled run completion. Disconnecting.")
			# Notify server via REST API to decrement client count
			if self._registered_with_server:
				try:
					endpoint = "/client-disconnect"
					utils._post(self.base_url, endpoint, {})
					self._registered_with_server = False
					log.info("Successfully notified server of client disconnect")
				except Exception as e:
					log.error(f"Failed to notify server of disconnect: {e}")
			# Then disconnect SocketIO
			self.sio.disconnect()

		@self.sio.on('node_ready')
		def on_node_ready(data):
			node_id = data.get('node_id')
			label = data.get('label')
			run_id = data.get('run_id')
			if self.run_id and run_id and run_id != self.run_id:
				log.debug("Ignoring node_ready for other run %s", run_id)
				return
			if node_id and label is not None:
				log.info(f"Received node_ready for {node_id}")
				thread = threading.Thread(target=self.execute_node, args=(node_id, label), daemon=True)
				thread.start()
			else:
				log.warning(f"Received invalid node_ready event: {data}")

	def set_node_status(self, node_id, status):
		"""Sends update to server to be processed by the graph worker queue."""
		try:
			payload = {
				"element_type": "node",
				"element_id": node_id,
				"value": status
			}
			if self.run_id:
				payload["run_id"] = self.run_id
			endpoint = "/edit-status"
			utils._post(self.base_url, endpoint, payload)
		except RuntimeError as e:
			log.error(f"Failed to set status {status} for {node_id}: {e}")

	def send_node_log(self, node_id, log_text):
		"""Sends captured log output to the server."""
		try:
			endpoint = "/save-node-log"
			utils._post(self.base_url, endpoint, {
				"node_id": node_id,
				"log": log_text
			})
		except RuntimeError as e:
			log.error(f"Failed to send log for {node_id}: {e}")

	def execute_node(self, node_id, label):
		"""Execute a single node: set running, run command, set ran/fail."""
		log.info(f"--> Executing node: {label} ({node_id})")
		try:
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

			log.debug(f"Executing command: {command}")
			process = subprocess.Popen(
				command,
				shell=True,
				stdout=subprocess.PIPE,
				stderr=subprocess.PIPE,
				text=True
			)
			stdout, stderr = process.communicate()

			log_text = f"STDOUT:\n{stdout}\nSTDERR:\n{stderr}".strip()
			self.send_node_log(node_id, log_text)

			if process.returncode == 0:
				log.info(f"--> Node {node_id} completed successfully")
				self.set_node_status(node_id, "ran")
			else:
				log.warning(f"!! Node {node_id} failed with exit code {process.returncode}")
				self.set_node_status(node_id, "fail")

		except Exception as e:
			error_log = f"[Runner internal error]\n{e}"
			self.send_node_log(node_id, error_log)
			log.error(f"!! Error executing {node_id}: {e}", exc_info=True)
			self.set_node_status(node_id, "fail")

	def start(self, initial_nodes=None):
		"""Connect to the server and start the run process."""
		log.info(f"Runner client starting for {self.base_url}")
		log.info(f"Initial nodes: {initial_nodes}")
		try:
			# Connect FIRST, then trigger the run
			log.info("Connecting to server via Socket.IO...")
			# SocketIO connects to server root, not workspace URL.
			# Derive server root (scheme://host:port) from the provided base_url.
			try:
				from urllib.parse import urlsplit
				split = urlsplit(self.base_url)
				server_url = f"{split.scheme}://{split.netloc}"
			except Exception:
				# Fallback to legacy constant if parsing fails
				server_url = utils.WORKSPACE_SERVER_URL
			self.sio.connect(server_url, transports=['websocket'], wait_timeout=10)
			
			# Register with server for this workspace
			try:
				endpoint = "/client-connect"
				utils._post(self.base_url, endpoint, {"workfile_path": self.workfile_path})
				self._registered_with_server = True
				log.info(f"Runner registered with workspace {self.workspace_id}")
			except Exception as e:
				log.error(f"Failed to register with workspace: {e}")
				self.sio.disconnect()
				return

			# Now that we're connected, initiate the run
			payload = {"nodes": initial_nodes or []}
			try:
				endpoint = "/run"
				log.info(f"Posting /run to server with payload: {payload}...")
				run_response = utils._post(self.base_url, endpoint, payload) or {}
				self.run_id = run_response.get("run_id")
				if self.run_id:
					log.info(f"Runner associated with run_id={self.run_id}")
				else:
					log.warning(f"No run_id in response: {run_response}")
			except Exception as e:
				log.error(f"Failed to POST /run after connecting: {e}")
				self.sio.disconnect()
				return

			# Wait for node_ready events
			log.info("Waiting for node_ready events...")
			self.sio.wait()
		except socketio.exceptions.ConnectionError as e:
			log.error(f"Connection error: {e}")
		except RuntimeError as e:
			log.error(f"Could not initiate run on server: {e}")
		except KeyboardInterrupt:
			log.info("\nStopping runner.")
		finally:
			# Always notify server and disconnect, even on error
			if self._registered_with_server:
				try:
					endpoint = "/client-disconnect"
					utils._post(self.base_url, endpoint, {})
					self._registered_with_server = False
					log.info("Runner cleanup: notified server of disconnect")
				except Exception as e:
					log.error(f"Runner cleanup: failed to notify server: {e}")
			
			if getattr(self.sio, "connected", False):
				self.sio.disconnect()
