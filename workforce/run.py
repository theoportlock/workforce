#!/usr/bin/env python
import socketio
import sys
import subprocess
import time
import requests

def edit_status(G, element_type, element_id, value):
    if element_type == 'node':
        if element_id not in G.nodes:
            raise ValueError(f"Node '{element_id}' not found in graph")
        G.nodes[element_id]['status'] = value
    elif element_type == 'edge':
        if element_id not in G.edges:
            raise ValueError(f"Edge '{element_id}' not found in graph")
        G.edges[element_id]['status'] = value
    return G

def save_graph(filename, graph):
    sio = socketio.Client()
    sio.connect('http://localhost:5000')
    sio.emit('graph_update', {"graph": graph, "filename": filename})
    sio.disconnect()
    resp = requests.post("http://localhost:5000/save-graph", json={"filename": filename, "graph": graph})
    if resp.status_code != 200:
        raise RuntimeError(f"Failed to save graph: {resp.text}")
    return resp.json()

def run_tasks(filename, prefix='', suffix=''):
    graph = requests.get("http://localhost:5000/graph").json()
    graph_prefix = graph.get('graph', {}).get('prefix', '')
    graph_suffix = graph.get('graph', {}).get('suffix', '')
    use_prefix = prefix if prefix else graph_prefix
    use_suffix = suffix if suffix else graph_suffix
    node_status = {n['id']: n.get('status', '') for n in graph['nodes']}
    run_nodes = [node for node, status in node_status.items() if status == 'run']
    node = run_nodes[0] if run_nodes else None
    if node:
        edit_status(graph['graph'], 'node', node, 'running')
        save_graph(filename, graph['graph'])
        subprocess.Popen([
            sys.executable, "-m", "workforce", "run_node",
            filename, node, "-p", use_prefix, "-s", use_suffix
        ])

def worker(filename, prefix='', suffix='', speed=0.5):
    graph = requests.get("http://localhost:5000/graph").json()
    graph_prefix = graph.get('graph', {}).get('prefix', '')
    graph_suffix = graph.get('graph', {}).get('suffix', '')
    use_prefix = prefix if prefix else graph_prefix
    use_suffix = suffix if suffix else graph_suffix
    initialize_pipeline(filename)
    status = ''
    while status != 'complete':
        time.sleep(speed)
        status = schedule_tasks(filename)
        run_tasks(filename, use_prefix, use_suffix)

def initialize_pipeline(filename):
    graph = requests.get("http://localhost:5000/graph").json()
    node_status = {n['id']: n.get('status', '') for n in graph['nodes']}
    failed_nodes = [node for node, status in node_status.items() if status == 'fail']
    for node in failed_nodes:
        edit_status(graph['graph'], 'node', node, 'run')
    if not node_status:
        # Find nodes with in-degree 0
        for node in graph['nodes']:
            node_id = node['id']
            indegree = sum(1 for e in graph['links'] if e['target'] == node_id)
            if indegree == 0:
                edit_status(graph['graph'], 'node', node_id, 'run')
    save_graph(filename, graph['graph'])

def schedule_tasks(filename):
    graph = requests.get("http://localhost:5000/graph").json()
    node_status = {n['id']: n.get('status', '') for n in graph['nodes']}
    ran_nodes = [node for node, status in node_status.items() if status == 'ran']
    # Set edge status for outgoing edges of ran nodes
    for node in ran_nodes:
        for link in graph['links']:
            if link['source'] == node:
                edit_status(graph['graph'], 'edge', (link['source'], link['target']), 'to_run')
        edit_status(graph['graph'], 'node', node, None)  # Remove status
    # Find ready nodes
    edge_status = {(l['source'], l['target']): l.get('status', '') for l in graph['links']}
    ready_nodes = []
    for node in graph['nodes']:
        node_id = node['id']
        indegree = sum(1 for l in graph['links'] if l['target'] == node_id)
        if indegree > 0:
            incoming = [l for l in graph['links'] if l['target'] == node_id]
            if all(edge_status.get((l['source'], l['target'])) == 'to_run' for l in incoming):
                ready_nodes.append(node_id)
    for node in ready_nodes:
        edit_status(graph['graph'], 'node', node, 'run')
        for l in graph['links']:
            if l['target'] == node:
                edit_status(graph['graph'], 'edge', (l['source'], l['target']), None)
    save_graph(filename, graph['graph'])
    node_status = {n['id']: n.get('status', '') for n in graph['nodes']}
    active_nodes = [node for node, status in node_status.items() if status in ('run', 'ran', 'running')]
    if not active_nodes:
        return 'complete'

def shell_quote_multiline(script: str) -> str:
    """Safely quote a multiline shell script '...'`."""
    return script.replace("'", "'\\''")

def run_node(filename, node, prefix='', suffix=''):
    graph = requests.get("http://localhost:5000/graph").json()
    graph_prefix = graph.get('graph', {}).get('prefix', '')
    graph_suffix = graph.get('graph', {}).get('suffix', '')
    use_prefix = prefix if prefix else graph_prefix
    use_suffix = suffix if suffix else graph_suffix
    label = None
    for n in graph['nodes']:
        if n['id'] == node:
            label = n.get('label', '')
            break
    quoted_label = shell_quote_multiline(label)
    command = f"{use_prefix}{quoted_label}{use_suffix}".strip()
    print(command)
    edit_status(graph['graph'], 'node', node, 'running')
    save_graph(filename, graph['graph'])
    try:
        subprocess.run(command, shell=True, check=True)
        edit_status(graph['graph'], 'node', node, 'ran')
    except subprocess.CalledProcessError:
        edit_status(graph['graph'], 'node', node, 'fail')
    save_graph(filename, graph['graph'])

def add_arguments(subparser):
    subparser.add_argument("filename", help="Workflow file")
    subparser.add_argument("--prefix", default="", help="Command prefix")
    subparser.add_argument("--suffix", default="", help="Command suffix")
    subparser.add_argument("--speed", type=float, default=1.0, help="Run speed multiplier")
    subparser.set_defaults(func=main)

def main(args=None):
    if not isinstance(args, argparse.Namespace):
        from argparse import Namespace
        filename = sys.argv[1] if len(sys.argv) > 1 else "Workfile.graphml"
        args = Namespace(filename=filename, prefix="", suffix="", speed=1.0)
    print(f"[Runner] Running {args.filename} with prefix={args.prefix}, suffix={args.suffix}")
    runner.worker(args.filename, args.prefix, args.suffix, args.speed)
