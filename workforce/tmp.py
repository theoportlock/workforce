#!/usr/bin/env python

import argparse
import networkx as nx
import matplotlib.pyplot as plt
import textwrap

import matplotlib as mpl
mpl.use('WebAgg')

def parse_args():
    """Parse command-line arguments for network visualization."""
    parser = argparse.ArgumentParser(description='Display network graph from GraphML')
    parser.add_argument('graphml_file', help='Input GraphML file')
    args = parser.parse_args()
    return args

def plot_network(graphml_file, max_label_width=150):
    G = nx.read_graphml(graphml_file)

    # Get node positions if available; otherwise, use a spring layout.
    if all('x' in G.nodes[node] and 'y' in G.nodes[node] for node in G.nodes):
        pos = {node: (float(G.nodes[node]['x']), -float(G.nodes[node]['y'])) for node in G.nodes}
    else:
        pos = nx.spring_layout(G)

    # Color mapping for statuses (for nodes and edges)
    status_colors = {
        'running': 'lightblue',
        'run': 'lightcyan',
        'ran': 'lightgreen',
        'fail': 'lightcoral'
    }

    # Node colors based on their 'status' attribute.
    node_colors = []
    for node in G.nodes:
        status = G.nodes[node].get('status', '').lower()
        node_colors.append(status_colors.get(status, 'lightgray'))

    # Edge colors based on their 'status' attribute.
    edge_colors = []
    for edge in G.edges:
        status = G.edges[edge].get('status', '').lower()
        # If the edge's status is 'to_run', override the color to black.
        if status == 'to_run':
            edge_colors.append('black')
        else:
            edge_colors.append(status_colors.get(status, 'lightgray'))

    # Function to wrap node labels.
    def wrap_label(text, max_pixels, font_size=6):
        max_chars = int(max_pixels / (font_size * 0.6))
        return "\n".join(textwrap.wrap(text, max_chars))

    labels = {node: wrap_label(G.nodes[node].get('label', node), max_label_width) for node in G.nodes}

    # Create the plot.
    fig, ax = plt.subplots(figsize=(5, 5))
    nx.draw(
        G,
        pos,
        labels=labels, 
        with_labels=True,
        node_color=node_colors,
        node_size=600,
        edge_color=edge_colors,
        font_size=6,
        arrows=True,
        arrowsize=12,
        ax=ax
    )
    
    return fig

def main():
    args = parse_args()
    fig = plot_network(args.graphml_file)

    # Define a key press event handler.
    def on_key(event):
        if event.key == 'q':
            plt.close(fig)

    # Connect the event handler to the figure.
    fig.canvas.mpl_connect('key_press_event', on_key)
    
    # Display the plot window; this call is blocking until the window is closed.
    plt.show()

if __name__ == "__main__":
    main()

