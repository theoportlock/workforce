#!/usr/bin/env python

from filelock import FileLock
from matplotlib.animation import FuncAnimation
import argparse
import networkx as nx
import textwrap
import time

import matplotlib as mpl
mpl.use('WebAgg')  # Set backend before importing pyplot
import matplotlib.pyplot as plt

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

def run_tasks(filename, prefix='bash -c'):
    with FileLock(f"{filename}.lock"):
        G = load(filename)
        node_status = nx.get_node_attributes(G, "status")
        run_nodes = {node for node, status in node_status.items() if status == 'run'}
        if run_nodes:
            node = run_nodes.pop()
            subprocess.Popen(["wf", "run_node", filename, node, "-p", prefix])

def worker(filename, prefix='bash -c', speed=0.5):
    status = ''
    while status != 'complete':
        time.sleep(speed)
        status = schedule_tasks(filename)
        run_tasks(filename, prefix)

def schedule_tasks(filename):
    G = load(filename)
    node_status = nx.get_node_attributes(G, "status")
    if not node_status:
        node_updates = {node:'run' for node, degree in G.in_degree() if degree == 0}
        nx.set_node_attributes(G, node_updates, 'status')
    else:
        ran_nodes = {node for node, status in node_status.items() if status == 'ran'}
        if ran_nodes:
            forward_edges = [(u, v) for node in ran_nodes for u, v in G.out_edges(node)]
            nx.set_edge_attributes(G, {edge: 'to_run' for edge in forward_edges}, 'status')
            [G.nodes[node].pop('status', None) for node in ran_nodes]
            edge_status = nx.get_edge_attributes(G, "status")
            ready_nodes = {
                node for node in G.nodes
                if G.in_degree(node) > 0 and
                all(edge_status.get((u, node)) == 'to_run' for u, _ in G.in_edges(node))}
            if ready_nodes:
                nx.set_node_attributes(G, {node: 'run' for node in ready_nodes}, 'status')
                reverse_edges = [(u, v) for node in ready_nodes for u, v in G.in_edges(node)]
                [G.edges[edge].pop('status', None) for edge in reverse_edges]
    save(G, filename)
    if not nx.get_node_attributes(G, "status"):
        return 'complete'

def run_node(filename, node, prefix='bash -c'):
    """Execute a command associated with a node and update its status."""
    G = load(filename)
    try:
        label = G.nodes[node].get('label', '')
        escaped_label = label.replace('"', '\\"')
        command = f"{prefix} \"{escaped_label}\""
        edit_status(filename,'node',node,'running')
        subprocess.run(command, shell=True, check=True)
        edit_status(filename,'node',node,'ran')
    except subprocess.CalledProcessError:
        edit_status(filename,'node',node,'fail')

def plot_network(filename, interval=100, max_label_width=150):
    fig, ax = plt.subplots(figsize=(5, 5))
    status_colors = {'running': 'lightblue', 'run': 'lightcyan', 'ran': 'lightgreen', 'fail': 'lightcoral'}

    def wrap_label(text, max_pixels, font_size=6):
        return "\n".join(textwrap.wrap(text, int(max_pixels / (font_size * 0.6))))

    G = load(filename)

    pos = {n: (float(G.nodes[n]['x']), -float(G.nodes[n]['y'])) for n in G if 'x' in G.nodes[n] and 'y' in G.nodes[n]}
    if not pos:
        pos = nx.spring_layout(G)
    def update(_):
        ax.clear()
        G = load(filename)
        node_colors = [status_colors.get(G.nodes[n].get('status', '').lower(), 'lightgray') for n in G]
        edge_colors = [
            'black' if G.edges[edge].get('status', '').lower() == 'to_run' else
            status_colors.get(G.edges[edge].get('status', '').lower(), 'lightgray')
            for edge in G.edges
        ]
        labels = {n: wrap_label(G.nodes[n].get('label', n), max_label_width) for n in G}
        nx.draw(G, pos, labels=labels, with_labels=True, node_color=node_colors, node_size=600,
                edge_color=edge_colors, font_size=6, arrows=True, arrowsize=12, ax=ax)
        fig.canvas.draw_idle()

    animation = FuncAnimation(fig, update, interval=interval, cache_frame_data=False)
    fig.canvas.mpl_connect('key_press_event', lambda e: plt.close(fig) if e.key == 'q' else None)
    plt.show()

def load(filename):
    with FileLock(f"{filename}.lock"):
        return nx.read_graphml(filename)

def save(G, filename):
    with FileLock(f"{filename}.lock"):
        nx.write_graphml(G, filename)

