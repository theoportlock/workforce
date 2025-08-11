#!/usr/bin/env python

import sys
import subprocess
import networkx as nx
import time
from .utils import GraphMLAtomic

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

def run_tasks(filename, prefix='bash -c ', suffix=''):
    with GraphMLAtomic(filename) as ga:
        G = ga.G
        node_status = nx.get_node_attributes(G, "status")
        run_nodes = {node for node, status in node_status.items() if status == 'run'}
        if run_nodes:
            node = run_nodes.pop()
            G.nodes[node]['status'] = 'running'
            ga.mark_modified()
        else:
            node = None
    if node:
        subprocess.Popen([
            sys.executable, "-m", "workforce", "run_node",
            filename, node, "-p", prefix, "-s", suffix
        ])

def worker(filename, prefix='bash -c ', suffix='', speed=0.5):
    initialize_pipeline(filename)
    status = ''
    while status != 'complete':
        time.sleep(speed)
        status = schedule_tasks(filename)
        run_tasks(filename, prefix, suffix)

def initialize_pipeline(filename):
    with GraphMLAtomic(filename) as ga:
        G = ga.G
        node_status = nx.get_node_attributes(G, "status")
        failed_nodes = {node for node, status in node_status.items() if status == 'fail'}
        if failed_nodes:
            nx.set_node_attributes(G, {node: 'run' for node in failed_nodes}, 'status')
            ga.mark_modified()
        if not node_status:
            node_updates = {node: 'run' for node, degree in G.in_degree() if degree == 0}
            nx.set_node_attributes(G, node_updates, 'status')
            ga.mark_modified()

def schedule_tasks(filename):
    with GraphMLAtomic(filename) as ga:
        G = ga.G
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
            ga.mark_modified()
        node_status = nx.get_node_attributes(G, "status")
        active_nodes = {node for node, status in node_status.items() if status in ('run', 'ran', 'running')}
    if not active_nodes:
        return 'complete'

def shell_quote_multiline(script: str) -> str:
    """Safely quote a multiline shell script for `bash -c '...'`."""
    return script.replace("'", "'\\''")

def run_node(filename, node, prefix='bash -c ', suffix=''):
    with GraphMLAtomic(filename) as ga:
        G = ga.G
        label = G.nodes[node].get('label', '')
        quoted_label = shell_quote_multiline(label)
        command = f"{prefix}{quoted_label}{suffix}".strip()
        print(command)
        G.nodes[node]['status'] = 'running'
        ga.mark_modified()
    try:
        subprocess.run(command, shell=True, check=True)
        with GraphMLAtomic(filename) as ga:
            ga.G.nodes[node]['status'] = 'ran'
            ga.mark_modified()
    except subprocess.CalledProcessError:
        with GraphMLAtomic(filename) as ga:
            ga.G.nodes[node]['status'] = 'fail'
            ga.mark_modified()