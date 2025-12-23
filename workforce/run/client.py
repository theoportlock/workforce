import socketio
import subprocess
import threading
import logging
import uuid

from workforce import utils

log = logging.getLogger(__name__)

class Runner:
	def __init__(self, base_url, wrapper="{}", client_id=None):
		self.base_url = base_url
		self.wrapper = wrapper
		self.run_id = None
		self.client_id = client_id or str(uuid.uuid4())
		self.sio = socketio.Client(logger=log.isEnabledFor(logging.DEBUG), engineio_logger=log.isEnabledFor(logging.DEBUG))
		self._setup_events()

	def _setup_events(self):
		@self.sio.event
		def connect():
			log.info(f"Runner connected to {self.base_url}")

		@self.sio.event
		def disconnect():
			log.info("Runner disconnected.")

		@self.sio.on('run_complete')
		def on_run_complete(data=None):
			run_id = None
			if isinstance(data, dict):
				run_id = data.get("run_id")
				client_id = data.get("client_id")
				if client_id and self.client_id and client_id != self.client_id:
					log.debug("Ignoring run_complete for other client %s", client_id)
					return
			if run_id and self.run_id and run_id != self.run_id:
				log.debug("Ignoring run_complete for other run_id %s", run_id)
				return
			log.info("Server signaled run completion. Disconnecting.")
			self.sio.disconnect()

		@self.sio.on('node_ready')
		def on_node_ready(data):
			node_id = data.get('node_id')
			label = data.get('label')
			run_id = data.get('run_id')
			client_id = data.get('client_id')
			if self.client_id and client_id and client_id != self.client_id:
				log.debug("Ignoring node_ready for other client %s", client_id)
				return
			if self.run_id and run_id and run_id != self.run_id:
				log.debug("Ignoring node_ready for other run %s", run_id)
				return
			if node_id and label is not None:
				log.info(f"Received node_ready for {node_id}")
				thread = threading.Thread(target=self.execute_node, args=(run_id, node_id, label), daemon=True)
				thread.start()
			else:
				log.warning(f"Received invalid node_ready event: {data}")

	def set_node_status(self, run_id, node_id, status):
		"""Sends update to server to be processed by the graph worker queue."""
		try:
			utils._post(self.base_url, "/edit-status", {
				"run_id": run_id,
				"element_type": "node",
				"element_id": node_id,
				"value": status
			})
		except RuntimeError as e:
			log.error(f"Failed to set status {status} for {node_id}: {e}")

	def get_graph(self):
		"""Fetches the current graph state from the server."""
		try:
			return utils._get(self.base_url, "/get-graph")
		except RuntimeError as e:
			log.error(f"Failed to get graph: {e}")
			return None

		def stop(self, selected_nodes=None, run_id=None):

			"""

			Stop running nodes for a given run.

	

			If `selected_nodes` is provided, only those nodes will be stopped.

			Otherwise, all nodes currently in the 'running' state will be stopped.

			Stopping a node sets its status to 'fail'.

			"""

			run_id = run_id or self.run_id

			if not run_id:

				log.error("Could not stop nodes: no run_id specified.")

				return

	

			log.info(f"Stopping nodes for run_id: {run_id}")

			graph_data = self.get_graph()

			if not graph_data:

				log.error("Could not stop nodes: failed to retrieve graph.")

				return

	

			nodes_to_stop = []

			if selected_nodes:

				log.info(f"Stopping selected nodes: {selected_nodes}")

				nodes_to_stop = selected_nodes

			else:

				log.info("Stopping all 'running' nodes.")

				for node in graph_data.get("nodes", []):

					if node.get("status") == "running":

						nodes_to_stop.append(node["id"])

	

			if not nodes_to_stop:

				log.info("No nodes to stop.")

				return

	

			for node_id in nodes_to_stop:

				log.info(f"Stopping node {node_id} by setting status to 'fail'.")

				self.set_node_status(run_id, node_id, "fail")

	

			log.info("Stop command sent for all targeted nodes.")

	def resume(self, selected_nodes=None, run_id=None):
		"""Resumes a run, optionally with a new selection of nodes."""
		run_id = run_id or self.run_id
		if not run_id:
			log.error("Could not resume: no run_id specified.")
			return

		log.info(f"Resuming run {run_id} with nodes: {selected_nodes or 'all'}")
		try:
			utils._post(self.base_url, "/resume", {
				"run_id": run_id,
				"nodes": selected_nodes or [],
				"client_id": self.client_id
			})
		except RuntimeError as e:
			log.error(f"Failed to resume run {run_id}: {e}")

	def send_node_log(self, node_id, log_text):
		"""Sends captured log output to the server."""
		try:
			utils._post(self.base_url, "/save-node-log", {
				"node_id": node_id,
				"log": log_text
			})
		except RuntimeError as e:
			log.error(f"Failed to send log for {node_id}: {e}")

	def execute_node(self, run_id, node_id, label):
		"""Execute a single node: set running, run command, set ran/fail."""
		log.info(f"--> Executing node: {label} ({node_id}) for run {run_id}")
		try:
			self.set_node_status(run_id, node_id, "running")

			if "{}" in self.wrapper:
				command = self.wrapper.replace("{}", utils.shell_quote_multiline(label))
			else:
				command = f"{self.wrapper} {utils.shell_quote_multiline(label)}"

			if not command.strip():
				log.info(f"--> Empty command for {node_id}, marking done.")
				self.send_node_log(node_id, "[No command to run]")
				self.set_node_status(run_id, node_id, "ran")
				return

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
				log.info(f"--> Finished execution for node: {label} ({node_id})")
				self.set_node_status(run_id, node_id, "ran")
			else:
				log.warning(f"!! Failed: {label} ({node_id})")
				self.set_node_status(run_id, node_id, "fail")

		except Exception as e:
			error_log = f"[Runner internal error]\n{e}"
			self.send_node_log(node_id, error_log)
			log.error(f"!! Error executing {node_id}: {e}", exc_info=True)
			self.set_node_status(run_id, node_id, "fail")

	def start(self, selected_nodes=None):
		"""Connect to the server and start the run process for a subset of nodes."""
		log.info(f"Runner client starting for {self.base_url}")
		try:
			# Initiate run explicitly and capture run_id
			payload = {"nodes": selected_nodes or [], "run_on_server": False, "client_id": self.client_id}
			try:
				log.info("Posting /run to server to initiate run...")
				run_response = utils._post(self.base_url, "/run", payload) or {}
				self.run_id = run_response.get("run_id")
				if self.run_id:
					log.info(f"Runner associated with run_id={self.run_id}")
			except Exception as e:
				log.warning(f"Failed to POST /run before connecting: {e}")

			log.info("Connecting to server via Socket.IO...")
			self.sio.connect(self.base_url, transports=['websocket'], wait_timeout=10)
			self.sio.wait()
		except socketio.exceptions.ConnectionError as e:
			log.error(f"Connection error: {e}")
		except RuntimeError as e:
			log.error(f"Could not initiate run on server: {e}")
		except KeyboardInterrupt:
			log.info("\nStopping runner.")
		finally:
			if getattr(self.sio, "connected", False):
				self.sio.disconnect()
