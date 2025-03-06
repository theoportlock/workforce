#!/usr/bin/env python

from filelock import FileLock, Timeout
from matplotlib.animation import FuncAnimation
import argparse
import sys
import subprocess
import networkx as nx
import textwrap
import time
import matplotlib as mpl
mpl.use('WebAgg')  # Set backend before importing pyplot
import matplotlib.pyplot as plt

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

def run_tasks(filename, prefix='bash -c', suffix=''):
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

def worker(filename, prefix='bash -c', suffix='', speed=0.5):
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

def run_node(filename, node, prefix='bash -c', suffix=''):
    with GraphMLAtomic(filename) as G:
        label = G.nodes[node].get('label', '')
        escaped_label = label.replace('"', '\\"')
        command = f"{prefix} \"{escaped_label}\" {suffix}"
        G.nodes[node]['status'] = 'running'
    try:
        subprocess.run(command, shell=True, check=True)
        with GraphMLAtomic(filename) as G: G.nodes[node]['status'] = 'ran'
    except subprocess.CalledProcessError:
        with GraphMLAtomic(filename) as G: G.nodes[node]['status'] = 'fail'


def safe_load(filename, lock_timeout=0.1):
    lock = FileLock(f"{filename}.lock")
    try:
        with lock.acquire(timeout=lock_timeout):
            return nx.read_graphml(filename)
    except Timeout:
        # Could not acquire the lock quickly; skip this update
        return None

def plot_network(filename, interval=200, max_label_width=150):
    G = safe_load(filename)
    if G is None:
        print("Could not acquire file lock at startup.")
        return

    fig, ax = plt.subplots(figsize=(5, 5))
    status_colors = {'running': 'lightblue', 'run': 'lightcyan', 'ran': 'lightgreen', 'fail': 'lightcoral'}

    def wrap_label(text, max_pixels, font_size=6):
        return "\n".join(textwrap.wrap(text, int(max_pixels / (font_size * 0.6))))

    pos = {n: (float(G.nodes[n]['x']), -float(G.nodes[n]['y']))
           for n in G if 'x' in G.nodes[n] and 'y' in G.nodes[n]}
    if not pos:
        pos = nx.spring_layout(G)

    def update(_):
        ax.clear()
        G_new = safe_load(filename)
        if G_new is None:
            # Skip this update if the lock could not be acquired.
            return
        # Use the same positions if possible.
        node_colors = [status_colors.get(G_new.nodes[n].get('status', '').lower(), 'lightgray') for n in G_new]
        edge_colors = [
            'black' if G_new.edges[edge].get('status', '').lower() == 'to_run' else
            status_colors.get(G_new.edges[edge].get('status', '').lower(), 'lightgray')
            for edge in G_new.edges
        ]
        labels = {n: wrap_label(G_new.nodes[n].get('label', n), max_label_width) for n in G_new}
        nx.draw(G_new, pos, labels=labels, with_labels=True, node_color=node_colors, node_size=600,
                edge_color=edge_colors, font_size=6, arrows=True, arrowsize=12, ax=ax)
        fig.canvas.draw_idle()

    animation = FuncAnimation(fig, update, interval=interval, cache_frame_data=False)
    fig.canvas.mpl_connect('key_press_event', lambda e: plt.close(fig) if e.key == 'q' else None)
    plt.show()

