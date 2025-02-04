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

    # Set node colors (lighter gray by default)
    node_color = 'lightgray'  # Changed to lighter gray
    if all('status' in G.nodes[node] for node in G.nodes):
        node_color = [G.nodes[node]['status'] for node in G.nodes]

    # Create wrapped labels
    def wrap_label(text, max_pixels, font_size=12):
        max_chars = int(max_pixels / (font_size * 0.6))
        return "\n".join(textwrap.wrap(text, max_chars))

    labels = {node: wrap_label(G.nodes[node].get('label', node), max_label_width) for node in G.nodes}

    # Draw and save graph
    plt.figure(figsize=(10, 10))
    nx.draw(G, pos,
            labels=labels, 
            with_labels=True,
            node_color=node_color,
            cmap=plt.cm.viridis,
            node_size=1200,
            edge_color='lightgray',  # Changed to lighter gray
            font_size=12,
            arrows=True,
            arrowsize=12)
    plt.savefig(output_file, format='pdf')
    plt.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate network graph PDF from GraphML')
    parser.add_argument('graphml_file', help='Input GraphML file')
    parser.add_argument('--output_file', default='network.pdf', help='Output PDF file')
    args = parser.parse_args()
    plot_network(args.graphml_file, args.output_file)
