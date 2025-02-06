#!/usr/bin/env python

import argparse
import networkx as nx
import matplotlib.pyplot as plt
import textwrap
import time

def parse_args():
    """Parse command-line arguments for network visualization."""
    parser = argparse.ArgumentParser(description='Continuously update network graph view from GraphML')
    parser.add_argument('graphml_file', help='Input GraphML file')
    parser.add_argument('--output_file', help='(Optional) Save a snapshot to a PDF file')
    args = parser.parse_args()
    return args

def plot_network(graphml_file, output_file=None, max_label_width=150):
    # Read the GraphML file each time to pick up any changes
    G = nx.read_graphml(graphml_file)

    # Get node positions or generate layout
    if all('x' in G.nodes[node] and 'y' in G.nodes[node] for node in G.nodes):
        pos = {node: (float(G.nodes[node]['x']), -float(G.nodes[node]['y'])) for node in G.nodes}
    else:
        pos = nx.spring_layout(G)

    # Color mapping for statuses for nodes (and some edges)
    status_colors = {
        'running': 'lightblue',
        'run': 'lightcyan',
        'ran': 'lightgreen',
        'fail': 'lightcoral'
    }

    # Node colors based on status
    node_colors = []
    for node in G.nodes:
        status = G.nodes[node].get('status', '').lower()
        node_colors.append(status_colors.get(status, 'lightgray'))

    # Edge colors based on status:
    # If an edge has status "to_run", color it black; otherwise use the mapping
    edge_colors = []
    for edge in G.edges:
        status = G.edges[edge].get('status', '').lower()
        if status == 'to_run':
            edge_colors.append('black')
        else:
            edge_colors.append(status_colors.get(status, 'lightgray'))

    # Create wrapped labels for nodes
    def wrap_label(text, max_pixels, font_size=6):
        max_chars = int(max_pixels / (font_size * 0.6))
        return "\n".join(textwrap.wrap(text, max_chars))
    
    labels = {node: wrap_label(G.nodes[node].get('label', node), max_label_width) for node in G.nodes}

    # Clear the current figure
    plt.clf()

    # Draw the network graph
    nx.draw(G, pos,
            labels=labels,
            with_labels=True,
            node_color=node_colors,
            node_size=600,
            edge_color=edge_colors,
            font_size=6,
            arrows=True,
            arrowsize=12)

    # Optionally save a snapshot as a PDF
    if output_file is not None:
        plt.savefig(output_file, format='pdf', bbox_inches='tight')

def main():
    args = parse_args()

    # Turn on interactive mode
    plt.ion()
    fig = plt.figure(figsize=(5, 5))

    try:
        while True:
            plot_network(args.graphml_file, args.output_file)
            # Redraw the canvas
            fig.canvas.draw()
            fig.canvas.flush_events()
            # Pause before next update (adjust time as needed)
            time.sleep(2)
    except KeyboardInterrupt:
        print("\nExiting network viewer.")

if __name__ == "__main__":
    main()
