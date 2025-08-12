#!/usr/bin/env python

from filelock import FileLock, Timeout
import sys
import subprocess
import networkx as nx
import time

class GraphMLAtomic:
    def __init__(self, filename):
        self.filename = filename
        self.lock = FileLock(f"{filename}.lock")
    def __enter__(self):
        self.lock.acquire()
        self.G = nx.read_graphml(self.filename)
        return self.G
    def __exit__(self, exc_type, exc_value, traceback):
        nx.write_graphml(self.G, self.filename)
        self.lock.release()

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

def run_tasks(filename, prefix='', suffix=''):
    with GraphMLAtomic(filename) as G:
        node_status = nx.get_node_attributes(G, "status")
        run_nodes = {node for node, status in node_status.items() if status == 'run'}
        if run_nodes:
            node = run_nodes.pop()
            G.nodes[node]['status'] = 'running'
        else:
            node = None
    if node:
        subprocess.Popen([
            sys.executable, "-m", "workforce", "run_node",
            filename, node, "-p", prefix, "-s", suffix
        ])

def worker(filename, prefix='', suffix='', speed=0.5):
    initialize_pipeline(filename)
    status = ''
    while status != 'complete':
        time.sleep(speed)
        status = schedule_tasks(filename)
        run_tasks(filename, prefix, suffix)

def initialize_pipeline(filename):
    with GraphMLAtomic(filename) as G:
        node_status = nx.get_node_attributes(G, "status")
        failed_nodes = {node for node, status in node_status.items() if status == 'fail'}
        if failed_nodes:
            nx.set_node_attributes(G, {node: 'run' for node in failed_nodes}, 'status')
        if not node_status:
            node_updates = {node: 'run' for node, degree in G.in_degree() if degree == 0}
            nx.set_node_attributes(G, node_updates, 'status')

def schedule_tasks(filename):
    with GraphMLAtomic(filename) as G:
        node_status = nx.get_node_attributes(G, "status")
        ran_nodes = {node for node, status in node_status.items() if status == 'ran'}
        if ran_nodes:
            forward_edges = [(u, v) for node in ran_nodes for u, v in G.out_edges(node)]
            nx.set_edge_attributes(G, {edge: 'to_run' for edge in forward_edges}, 'status')
            [G.nodes[node].pop('status', None) for node in ran_nodes]
            edge_status = nx.get_edge_attributes(G, "status")
            ready_nodes = {
                node for node in G.nodes
                if G.in_degree(node) > 0 and
                all(edge_status.get((u, node)) == 'to_run' for u, _ in G.in_edges(node))
            }
            if ready_nodes:
                nx.set_node_attributes(G, {node: 'run' for node in ready_nodes}, 'status')
                reverse_edges = [(u, v) for node in ready_nodes for u, v in G.in_edges(node)]
                [G.edges[edge].pop('status', None) for edge in reverse_edges]
        node_status = nx.get_node_attributes(G, "status")
        active_nodes = {node for node, status in node_status.items() if status in ('run', 'ran', 'running')}
    if not active_nodes:
        return 'complete'

def shell_quote_multiline(script: str) -> str:
    """Safely quote a multiline shell script '...'`."""
    return script.replace("'", "'\\''")

def run_node(filename, node, prefix='', suffix=''):
    with GraphMLAtomic(filename) as G:
        label = G.nodes[node].get('label', '')
        quoted_label = shell_quote_multiline(label)
        command = f"{prefix}{quoted_label}{suffix}".strip()
        print(command)
        G.nodes[node]['status'] = 'running'
    try:
        subprocess.run(command, shell=True, check=True)
        with GraphMLAtomic(filename) as G: G.nodes[node]['status'] = 'ran'
    except subprocess.CalledProcessError:
        with GraphMLAtomic(filename) as G: G.nodes[node]['status'] = 'fail'
