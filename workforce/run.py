#!/usr/bin/env python
import socketio
import sys
import subprocess
import time
import requests
import threading
import argparse

# Initialize SocketIO Client
sio = socketio.Client()

# Global configuration
CONFIG = {
    "url": "",
    "prefix": "",
    "suffix": ""
}

def get_prefix_suffix(graph, prefix='', suffix=''):
    graph_prefix = graph.get('graph', {}).get('prefix', '')
    graph_suffix = graph.get('graph', {}).get('suffix', '')
    use_prefix = prefix if prefix else graph_prefix
    use_suffix = suffix if suffix else graph_suffix
    return use_prefix, use_suffix

def shell_quote_multiline(script: str) -> str:
    return script.replace("'", "'\\''")

def run_tasks():
    """
    Check for nodes with status='run' and execute them.
    """
    url = CONFIG['url']
    try:
        graph = requests.get(url).json()
    except Exception:
        return

    use_prefix, use_suffix = get_prefix_suffix(graph, CONFIG['prefix'], CONFIG['suffix'])

    node_status = {n['id']: n.get('status', '') for n in graph['nodes']}
    run_nodes = [node for node, status in node_status.items() if status == 'run']

    # Pick the first available node
    node = run_nodes[0] if run_nodes else None

    if node:
        print(f"--> Executing node: {node}")
        requests.post(f"{url}/update_status", json={"element_type": "node", "element_id": node, "status": "running"})

        # We actually run the logic here instead of calling the endpoint /run_node
        # to keep the logic contained in the runner, or we can call the logic function directly.
        # Below mirrors the logic in your original 'run_node' function:

        label = next((n.get('label', '') for n in graph['nodes'] if n['id'] == node), '')
        quoted_label = shell_quote_multiline(label)
        command = f"{use_prefix}{quoted_label}{use_suffix}".strip()

        try:
            subprocess.run(command, shell=True, check=True)
            print(f"--> Finished node: {node}")
            requests.post(f"{url}/update_status", json={"element_type": "node", "element_id": node, "status": "ran"})
        except subprocess.CalledProcessError:
            print(f"!! Failed node: {node}")
            requests.post(f"{url}/update_status", json={"element_type": "node", "element_id": node, "status": "fail"})

def schedule_tasks():
    """
    Check for nodes with status='ran', unlock their neighbors, and clean up.
    """
    url = CONFIG['url']
    try:
        graph = requests.get(url).json()
    except Exception:
        return

    node_status = {n['id']: n.get('status', '') for n in graph['nodes']}
    ran_nodes = [node for node, status in node_status.items() if status == 'ran']

    # 1. For every 'ran' node, mark outgoing edges as 'to_run'
    for node in ran_nodes:
        for link in graph['links']:
            if link['source'] == node:
                requests.post(f"{url}/update_status", json={"element_type": "edge", "element_id": [link['source'], link['target']], "status": "to_run"})
        # Clear status of the node itself so we don't process it again
        requests.post(f"{url}/update_status", json={"element_type": "node", "element_id": node, "status": None})

    # Refresh graph after updates above
    graph = requests.get(url).json()
    edge_status = {(l['source'], l['target']): l.get('status', '') for l in graph['links']}

    # 2. Find nodes where ALL incoming edges are 'to_run'
    ready_nodes = []
    for node in graph['nodes']:
        node_id = node['id']
        indegree = sum(1 for l in graph['links'] if l['target'] == node_id)
        if indegree > 0:
            incoming = [l for l in graph['links'] if l['target'] == node_id]
            if all(edge_status.get((l['source'], l['target'])) == 'to_run' for l in incoming):
                ready_nodes.append(node_id)

    # 3. Activate ready nodes
    for node in ready_nodes:
        print(f"--> Scheduling node: {node}")
        requests.post(f"{url}/update_status", json={"element_type": "node", "element_id": node, "status": "run"})
        # Clean up edges
        for l in graph['links']:
            if l['target'] == node:
                requests.post(f"{url}/update_status", json={"element_type": "edge", "element_id": [l['source'], l['target']], "status": None})

    # Check completion
    graph = requests.get(url).json()
    node_status = {n['id']: n.get('status', '') for n in graph['nodes']}
    active_nodes = [node for node, status in node_status.items() if status in ('run', 'ran', 'running')]

    if not active_nodes:
        print("== Pipeline Complete ==")
        # Optional: sys.exit(0) or keep listening for new nodes added manually

def initialize_pipeline(url):
    print("Initializing pipeline...")
    graph = requests.get(url).json()
    node_status = {n['id']: n.get('status', '') for n in graph['nodes']}

    failed_nodes = [node for node, status in node_status.items() if status == 'fail']
    for node in failed_nodes:
        requests.post(f"{url}/update_status", json={"element_type": "node", "element_id": node, "status": "run"})

    if not node_status:
        for node in graph['nodes']:
            node_id = node['id']
            indegree = sum(1 for e in graph['links'] if e['target'] == node_id)
            if indegree == 0:
                requests.post(f"{url}/update_status", json={"element_type": "node", "element_id": node_id, "status": "run"})

# --- SocketIO Event Handlers ---

@sio.event
def connect():
    print("Connected to server.")
    # Run initialization in a thread so we don't block the connect handler
    threading.Thread(target=initialize_pipeline, args=(CONFIG['url'],)).start()

@sio.event
def disconnect():
    print("Disconnected from server.")

@sio.on('node_ready')
def on_node_ready(data):
    print(f"Event received: Node {data.get('node_id')} is ready.")
    # Run execution in a separate thread to keep socket heartbeat alive
    threading.Thread(target=run_tasks).start()

@sio.on('node_done')
def on_node_done(data):
    print(f"Event received: Node {data.get('node_id')} finished.")
    # Run scheduling in a separate thread
    threading.Thread(target=schedule_tasks).start()

# --- Main ---

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("url", help="URL of the workforce server (e.g. http://127.0.0.1:8000/get-graph)")
    parser.add_argument("--prefix", default="", help="Command prefix")
    parser.add_argument("--suffix", default="", help="Command suffix")
    args = parser.parse_args()

    # Clean up URL to get base root
    base_url = args.url.replace("/get-graph", "").rstrip("/")

    CONFIG['url'] = base_url
    CONFIG['prefix'] = args.prefix
    CONFIG['suffix'] = args.suffix

    print(f"Connecting to {base_url}...")

    try:
        sio.connect(base_url)
        sio.wait() # Keeps the script running
    except KeyboardInterrupt:
        print("Stopping runner.")
        sio.disconnect()

if __name__ == "__main__":
    main()
