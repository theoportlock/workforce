#!/usr/bin/env python
import os
import subprocess
import networkx as nx
from filelock import FileLock
import argparse

def update_node_status(filename, node, status):
    """Update the status of a node in the GraphML file."""
    with FileLock(f"{filename}.lock"):
        G = nx.read_graphml(filename)
        nx.set_node_attributes(G, {node: status}, 'status')
        nx.write_graphml(G, filename)

def run_node(filename, node, prefix='bash -c'):
    """Execute a command associated with a node and update its status."""
    G = nx.read_graphml(filename)
    update_node_status(filename, node, 'running')

    try:
        label = G.nodes[node].get('label', '')
        escaped_label = label.replace('"', '\\"')
        command = f"{prefix} \"{escaped_label}\""
        subprocess.run(command, shell=True, check=True)
        update_node_status(filename, node, 'ran')
    except subprocess.CalledProcessError:
        update_node_status(filename, node, 'fail')

def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Run a node's associated command.")
    parser.add_argument("filename", type=str, help="Path to the input GraphML file.")
    parser.add_argument("node", type=str, help="Node to execute.")
    parser.add_argument("--prefix", '-p', default='bash -c', required=False, type=str, help="Prefix for command execution.")
    return parser.parse_args()

if __name__ == '__main__':
    args = parse_arguments()
    run_node(args.filename, args.node, args.prefix)
