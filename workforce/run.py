#!/usr/bin/env python
import socketio
import subprocess
import requests
import threading
import argparse
import os
from workforce import utils

# Initialize SocketIO Client
sio = socketio.Client()

# Global configuration
CONFIG = {
    "base_url": "",
    "prefix": "",
    "suffix": ""
}

# --- API Helpers ---

def get_graph_safe():
    """Fetch graph from server to get labels/commands."""
    try:
        resp = requests.get(f"{CONFIG['base_url']}/get-graph", timeout=2)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[Error] Could not fetch graph: {e}")
        return None

def set_node_status(node_id, status):
    """Sends update to server."""
    url = f"{CONFIG['base_url']}/edit-status"
    payload = {"element_type": "node", "element_id": node_id, "value": status}
    try:
        requests.post(url, json=payload, timeout=2)
    except Exception as e:
        print(f"[Error] Failed to set status {status} for {node_id}: {e}")

def send_node_log(node_id, log_text):
    """Sends captured log output to the server."""
    url = f"{CONFIG['base_url']}/save-node-log"
    payload = {"node_id": node_id, "log": log_text}
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"[Error] Failed to send log for {node_id}: {e}")

def shell_quote_multiline(script: str) -> str:
    return script.replace("'", "'\\''")

# --- Core Logic ---

def execute_specific_node(node_id):
    """Execute a single node: set running, run command, set ran/fail."""
    graph = get_graph_safe()
    if not graph:
        return

    node = next((n for n in graph['nodes'] if n['id'] == node_id), None)
    if not node:
        print(f"[Error] Server asked to run {node_id}, but it is not in the graph.")
        return

    if node.get('status') in ['running', 'ran']:
        print(f"[Skip] Node {node_id} is already {node.get('status')}.")
        return

    print(f"--> Executing node: {node.get('label', node_id)}")
    set_node_status(node_id, "running")

    label = node.get('label', '')
    command = f"{CONFIG['prefix']}{shell_quote_multiline(label)}{CONFIG['suffix']}".strip()

    if not command:
        print(f"--> Empty command for {node_id}, marking done.")
        set_node_status(node_id, "ran")
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
        
        # --- MODIFICATION START ---
        # Simply concatenate stdout and stderr with a single newline separator.
        # This removes the "STDOUT:\n" and "STDERR:\n" headers.
        log_text = f"{stdout}\n{stderr}"
        send_node_log(node_id, log_text)
        # --- MODIFICATION END ---

        if process.returncode == 0:
            print(f"--> Finished: {node.get('label', node_id)}")
            set_node_status(node_id, "ran")
        else:
            print(f"!! Failed: {node.get('label', node_id)}")
            set_node_status(node_id, "fail")

    except Exception as e:
        send_node_log(node_id, f"[Runner internal error]\n{e}")
        print(f"!! Error executing {node_id}: {e}")
        set_node_status(node_id, "fail")

def check_dependencies_and_schedule(finished_node_id):
    """Check children of finished node; mark ready nodes as 'run'."""
    graph = get_graph_safe()
    if not graph:
        return

    status_map = {n['id']: n.get('status', '') for n in graph['nodes']}
    children_ids = [l['target'] for l in graph['links'] if l['source'] == finished_node_id]

    for child_id in children_ids:
        child_status = status_map.get(child_id)
        if child_status in ['ran', 'run', 'running', 'fail']:
            continue

        incoming_links = [l for l in graph['links'] if l['target'] == child_id]
        if all(status_map.get(l['source']) == 'ran' for l in incoming_links):
            print(f"--> Dependencies met for {child_id}. Requesting run...")
            set_node_status(child_id, "run")

def scan_for_abandoned_tasks(graph):
    """Resume pipeline, works even if graph has cycles."""
    print("[scan] Checking pipeline state...")

    nodes = graph["nodes"]
    links = graph["links"]
    node_status = {n["id"]: n.get("status") for n in nodes}

    # Restart failed nodes
    # Also pick up any nodes that are already marked as 'run'
    ready_to_run_nodes = [nid for nid, status in node_status.items() if status == "run"]
    if ready_to_run_nodes:
        print(f"[scan] Found pre-marked nodes to run: {ready_to_run_nodes}")
        for nid in ready_to_run_nodes:
            sio.emit("node_ready", {"node_id": nid}) # Directly trigger execution
        return

    failed_nodes = [nid for nid, status in node_status.items() if status == "fail"]
    if failed_nodes:
        print(f"[scan] Restarting failed nodes: {failed_nodes}")
        for nid in failed_nodes:
            set_node_status(nid, "run")
        return

    # Build parent lookup
    node_parents = {n["id"]: [] for n in nodes}
    for l in links:
        node_parents[l["target"]].append(l["source"])

    # Try to schedule nodes
    runnable = []
    for nid, status in node_status.items():
        if status in ['ran', 'running', 'run']:
            continue
        parents = node_parents.get(nid, [])
        # Only consider parents that exist in the graph
        if all(node_status.get(p) == 'ran' for p in parents):
            runnable.append(nid)

    if runnable:
        print(f"[scan] Found runnable nodes: {runnable}")
        for nid in runnable:
            set_node_status(nid, "run")
        return

    # If nothing is runnable, see if there are nodes with no parents (roots) that are empty
    roots = [n["id"] for n in nodes if not node_parents.get(n["id"]) and node_status.get(n["id"]) is None]
    if roots:
        print(f"[scan] Starting root nodes: {roots}")
        for nid in roots:
            set_node_status(nid, "run")
        return

    print("[scan] Nothing to run.")


# --- SocketIO Event Handlers ---

@sio.event
def connect():
    print(f"[SocketIO] Connected to {CONFIG['base_url']}")
    graph = get_graph_safe()
    if graph:
        threading.Thread(target=scan_for_abandoned_tasks, args=(graph,), daemon=True).start()
    else:
        print("[scan] Cannot fetch graph on connect.")

@sio.event
def disconnect():
    print("[SocketIO] Disconnected.")

@sio.on('node_ready')
def on_node_ready(data):
    node_id = data.get('node_id')
    if node_id:
        threading.Thread(target=execute_specific_node, args=(node_id,), daemon=True).start()

@sio.on('node_done')
def on_node_done(data):
    node_id = data.get('node_id')
    if node_id:
        threading.Thread(target=check_dependencies_and_schedule, args=(node_id,), daemon=True).start()

def main(base_url, prefix="", suffix=""):
    base = base_url.replace("/get-graph", "").rstrip("/")
    CONFIG['base_url'] = base
    CONFIG['prefix'] = prefix
    CONFIG['suffix'] = suffix

    print(f"Runner connecting to {base}...")

    try:
        sio.connect(base, transports=['websocket'], wait_timeout=10)
        sio.wait()
    except Exception as e:
        print(f"Connection error: {e}")
    except KeyboardInterrupt:
        print("Stopping runner.")
        sio.disconnect()
