#!/usr/bin/env python

import argparse
import networkx as nx
import matplotlib.pyplot as plt
import textwrap
import matplotlib as mpl
from filelock import FileLock
from matplotlib.animation import FuncAnimation

mpl.use('WebAgg')

# Global variable to store the animation
_animation = None  

def parse_args():
    """Parse command-line arguments for network visualization."""
    parser = argparse.ArgumentParser(description='Display network graph from GraphML')
    parser.add_argument('filename', help='Input GraphML file')
    return parser.parse_args()

def wrap_label(text, max_pixels, font_size=6):
    """Wrap node labels to fit within a given width."""
    max_chars = int(max_pixels / (font_size * 0.6))
    return "\n".join(textwrap.wrap(text, max_chars))

def plot_network(filename, interval=100, max_label_width=150):
    """
    Load and display the network graph with automatic updates.

    Parameters:
        filename (str): Path to the GraphML file.
        interval (int): Update interval in milliseconds.
        max_label_width (int): Maximum width for node labels.
    """
    global _animation  # Prevent garbage collection

    fig, ax = plt.subplots(figsize=(5, 5))

    def update(_):
        ax.clear()  # Clear the axis to prevent over-plotting

        with FileLock(f"{filename}.lock"):
            G = nx.read_graphml(filename)

        # Determine node positions
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

        # Assign colors based on node and edge statuses
        node_colors = [status_colors.get(G.nodes[node].get('status', '').lower(), 'lightgray') for node in G.nodes]
        edge_colors = ['black' if G.edges[edge].get('status', '').lower() == 'to_run' else 
                       status_colors.get(G.edges[edge].get('status', '').lower(), 'lightgray') for edge in G.edges]

        # Generate wrapped labels
        labels = {node: wrap_label(G.nodes[node].get('label', node), max_label_width) for node in G.nodes}

        # Draw network
        nx.draw(
            G, pos, labels=labels, with_labels=True, node_color=node_colors, node_size=600,
            edge_color=edge_colors, font_size=6, arrows=True, arrowsize=12, ax=ax
        )

        fig.canvas.draw_idle()

    # Store the animation in a global variable
    _animation = FuncAnimation(fig, update, interval=interval)

    # Handle key press events (press 'q' to quit)
    def on_key(event):
        if event.key == 'q':
            plt.close(fig)

    fig.canvas.mpl_connect('key_press_event', on_key)
    
    # Start the WebAgg server
    plt.show()

def main():
    args = parse_args()
    plot_network(args.filename)

if __name__ == "__main__":
    main()

