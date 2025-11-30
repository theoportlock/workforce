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
    """
    Sends update to server.
    Server expects: {"element_type": "node", "element_id": ..., "value": ...}
    """
    url = f"{CONFIG['base_url']}/edit-status"
    payload = {
        "element_type": "node",
        "element_id": node_id,
        "value": status
    }
    try:
        requests.post(url, json=payload, timeout=2)
    except Exception as e:
        print(f"[Error] Failed to set status {status} for {node_id}: {e}")

def send_node_log(node_id, log_text):
    """Sends captured log output to the server."""
    url = f"{CONFIG['base_url']}/save-node-log"
    payload = {"node_id": node_id, "log": log_text}
    try:
        # Using a slightly longer timeout for potentially large logs
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"[Error] Failed to send log for {node_id}: {e}")

def shell_quote_multiline(script: str) -> str:
    return script.replace("'", "'\\''")

# --- Core Logic ---

def execute_specific_node(node_id):
    """
    The core worker. 
    1. Fetches node details (label/command).
    2. Sets status -> 'running'.
    3. Runs command.
    4. Sets status -> 'ran' or 'fail'.
    """
    graph = get_graph_safe()
    if not graph:
        return

    # Find the specific node data by ID
    node = next((n for n in graph['nodes'] if n['id'] == node_id), None)
    
    if not node:
        print(f"[Error] Server asked to run {node_id}, but it is not in the graph.")
        return

    # Check if we are already running or ran (prevent double execution)
    # Although server logic helps, client double-check is good.
    if node.get('status') in ['running', 'ran']:
        print(f"[Skip] Node {node_id} is already {node.get('status')}.")
        return

    print(f"--> Executing node: {node.get('label', node_id)}")
    
    # 1. Mark as running (UI turns Blue)
    set_node_status(node_id, "running")

    # 2. Construct Command
    label = node.get('label', '')
    use_prefix = CONFIG['prefix']
    use_suffix = CONFIG['suffix']
    
    quoted_label = shell_quote_multiline(label)
    command = f"{use_prefix}{quoted_label}{use_suffix}".strip()

    if not command:
        print(f"--> Empty command for {node_id}, marking done.")
        set_node_status(node_id, "ran")
        return

    # 3. Execute Subprocess
    try:
        # Use Popen to capture stdout/stderr
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate()

        # Combine stdout + stderr into a single log string
        log_text = f"STDOUT:\n{stdout}\n\nSTDERR:\n{stderr}"
        send_node_log(node_id, log_text)

        # Set status based on the subprocess return code
        if process.returncode == 0:
            print(f"--> Finished: {node.get('label', node_id)}")
            set_node_status(node_id, "ran")
            # Note: We do NOT call check_dependencies here directly.
            # The 'ran' status update will trigger 'node_done' event from server.
        else:
            print(f"!! Failed: {node.get('label', node_id)}")
            set_node_status(node_id, "fail")

    except Exception as e:
        send_node_log(node_id, f"[Runner internal error]\n{e}")
        print(f"!! Error executing {node_id}: {e}")
        set_node_status(node_id, "fail")

def check_dependencies_and_schedule(finished_node_id):
    """
    Triggered when a node finishes ('ran').
    We look at the graph. If a child node has ALL parents 'ran', we set it to 'run'.
    Setting it to 'run' will cause the Server to emit 'node_ready', closing the loop.
    """
    graph = get_graph_safe()
    if not graph:
        return

    status_map = {n['id']: n.get('status', '') for n in graph['nodes']}

    # Find all nodes that depend on the finished node
    # (Optimization: only look at children of the finished node)
    outgoing_edges = [l for l in graph['links'] if l['source'] == finished_node_id]
    children_ids = [l['target'] for l in outgoing_edges]

    for child_id in children_ids:
        child_status = status_map.get(child_id)

        # Skip if already done or running
        if child_status in ['ran', 'run', 'running', 'fail']:
            continue

        # Check inputs for this child
        incoming_links = [l for l in graph['links'] if l['target'] == child_id]
        parents_all_ran = True
        
        for link in incoming_links:
            parent_id = link['source']
            if status_map.get(parent_id) != 'ran':
                parents_all_ran = False
                break
        
        if parents_all_ran:
            print(f"--> Dependencies met for {child_id}. Requesting run...")
            # WE DO NOT RUN IT HERE. We tell the server to mark it 'run'.
            # The server will then emit 'node_ready', and on_node_ready will fire.
            set_node_status(child_id, "run")

def scan_for_abandoned_tasks():
    """
    Run ONCE at startup.
    Finds nodes that are stuck in 'run' (from a previous crash) and runs them.
    """
    graph = get_graph_safe()
    if not graph:
        return
    
    for node in graph['nodes']:
        if node.get('status') == 'run':
            print(f"[Startup] Found pending node {node['id']}, queuing...")
            threading.Thread(target=execute_specific_node, args=(node['id'],)).start()

# --- SocketIO Event Handlers ---

@sio.event
def connect():
    print(f"[SocketIO] Connected to {CONFIG['base_url']}")
    # Check if there were tasks waiting while we were offline
    threading.Thread(target=scan_for_abandoned_tasks).start()

@sio.event
def disconnect():
    print("[SocketIO] Disconnected.")

@sio.on('node_ready')
def on_node_ready(data):
    """
    CRITICAL: This is the trigger.
    Server says: Node X status changed to 'run'.
    We say: Okay, I will execute Node X.
    """
    node_id = data.get('node_id')
    if node_id:
        # Run in thread to prevent blocking the socket listener
        threading.Thread(target=execute_specific_node, args=(node_id,)).start()

@sio.on('node_done')
def on_node_done(data):
    """
    Server says: Node X status changed to 'ran'.
    We say: Okay, I will check if Node X's children can run now.
    """
    node_id = data.get('node_id')
    if node_id:
        threading.Thread(target=check_dependencies_and_schedule, args=(node_id,)).start()

# Accept the args object passed by the outer 'wf' entrypoint.
def main(args=None): 
    
    # 1. Setup Argument Parser for Local or Wrapper Use
    parser = argparse.ArgumentParser()
    parser.add_argument("url_or_path", help="URL of the workforce server (e.g. http://127.0.0.1:5000) or a path to a Workfile.")
    parser.add_argument("--prefix", default="", help="Command prefix")
    parser.add_argument("--suffix", default="", help="Command suffix")
    
    # If called directly (args is None) or we need to re-parse (e.g., using sys.argv),
    # otherwise use the passed args object.
    if args is None:
        args = parser.parse_args()
    
    # 2. Resolve URL from Argument
    input_value = args.url_or_path
    base_url = ""
    
    if input_value.startswith("http"):
        # Case A: User explicitly provided a URL
        base_url = input_value
        print(f"Runner using explicit URL: {base_url}")
    else:
        # Case B: Treat as a Workfile path
        
        # Check if the input value points to a real file path
        if not os.path.exists(input_value):
            # If not a file, it might still be a URL without http:// prefix
            # However, for simplicity and adherence to the request, 
            # we'll assume non-existent paths are an error for now.
             print(f"[Error] '{input_value}' is not a valid URL (missing http://) and not a file path.", file=sys.stderr)
             sys.exit(1)
            
        try:
            # Try to resolve the path to a port using the registry
            # We don't care about the returned path, just the port.
            _, port = utils.resolve_port(input_value)
            base_url = f"http://127.0.0.1:{port}"
            print(f"Runner resolved path '{input_value}' to server at {base_url}")
        except SystemExit:
            # resolve_port prints the error and calls sys.exit(1) if server is not found
            # We re-raise the exit.
            raise 

    # 3. Apply Configuration and Connect
    # Normalize URL (This is still necessary for /get-graph stripping)
    base = base_url.replace("/get-graph", "").rstrip("/")
    
    CONFIG['base_url'] = base
    CONFIG['prefix'] = args.prefix
    CONFIG['suffix'] = args.suffix

    print(f"Runner starting. Waiting for events from {base}...")
    
    try:
        # Using threading mode to ensure compatibility
        sio.connect(base, wait_timeout=10)
        sio.wait()
    except Exception as e:
        print(f"Connection error: {e}")
    except KeyboardInterrupt:
        print("Stopping runner.")
        sio.disconnect()
