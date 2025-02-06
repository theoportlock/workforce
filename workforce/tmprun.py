#!/usr/bin/env python
import os
import subprocess
import networkx as nx
from filelock import FileLock
import argparse

def update_node_status(filename, node, status):
    """Safely update the status of a node while allowing parallel execution."""
    lockfile = f"{filename}.lock"

    with FileLock(lockfile):  # Only lock for writing
        G = nx.read_graphml(filename)

        if node not in G.nodes:
            print(f"Warning: Node {node} not found in {filename}")
            return

        G.nodes[node]['status'] = status
        nx.write_graphml(G, filename)

def run_node(filename, node, prefix='bash -c'):
    """Execute a command associated with a node while allowing parallel execution."""
    G = nx.read_graphml(filename)  # No lock needed for reading

    if node not in G.nodes:
        print(f"Error: Node {node} not found in {filename}")
        return

    # Get the command label associated with the node
    command = G.nodes[node].get('label', '').strip()

    if not command:
        print(f"Warning: Node {node} has no command to run.")
        return

    # Update status to 'running' (LOCKED)
    update_node_status(filename, node, 'running')

    try:
        print(f"Executing command: {command}")  # Debugging output
        subprocess.run(command, shell=True, check=True)  # Actually runs the command

        # Update status to 'ran' (LOCKED)
        update_node_status(filename, node, 'ran')

    except subprocess.CalledProcessError:
        print(f"Error executing command for node {node}")

        # Update status to 'fail' (LOCKED)
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

