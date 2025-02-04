#!/usr/bin/env python

import argparse
import networkx as nx
import matplotlib.pyplot as plt
import textwrap

def plot_network(graphml_file, output_file, max_label_width=150):
    G = nx.read_graphml(graphml_file)

    # Get node positions or generate layout
    if all('x' in G.nodes[node] and 'y' in G.nodes[node] for node in G.nodes):
        pos = {node: (float(G.nodes[node]['x']), -float(G.nodes[node]['y'])) for node in G.nodes}
    else:
        pos = nx.spring_layout(G)

    # Color mapping for statuses
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

    # Edge colors based on status
    edge_colors = []
    for edge in G.edges:
        status = G.edges[edge].get('status', '').lower()
        edge_colors.append(status_colors.get(status, 'lightgray'))

    # Create wrapped labels
    def wrap_label(text, max_pixels, font_size=6):
        max_chars = int(max_pixels / (font_size * 0.6))
        return "\n".join(textwrap.wrap(text, max_chars))

    labels = {node: wrap_label(G.nodes[node].get('label', node), max_label_width) for node in G.nodes}

    # Draw and save graph
    plt.figure(figsize=(5, 5))
    nx.draw(G, pos,
            labels=labels, 
            with_labels=True,
            node_color=node_colors,
            node_size=600,
            edge_color=edge_colors,
            font_size=6,
            arrows=True,
            arrowsize=12,
            #connectionstyle='arc3,rad=0.1')  # For better curved edges
            )
    
    plt.savefig(output_file, format='pdf', bbox_inches='tight')
    plt.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate network graph PDF from GraphML')
    parser.add_argument('graphml_file', help='Input GraphML file')
    parser.add_argument('--output_file', default='network.pdf', help='Output PDF file')
    args = parser.parse_args()
    plot_network(args.graphml_file, args.output_file)
