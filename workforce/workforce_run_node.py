#!/usr/bin/env python

from workforce_edit_element import edit_element_status
from filelock import FileLock
import argparse
import networkx as nx
import subprocess

def run_node(filename, node, prefix='bash -c'):
    """Execute a command associated with a node and update its status."""
    G = nx.read_graphml(filename)
    try:
        label = G.nodes[node].get('label', '')
        escaped_label = label.replace('"', '\\"')
        command = f"{prefix} \"{escaped_label}\""
        edit_element_status(filename,'node',node,'running')
        subprocess.run(command, shell=True, check=True)
        edit_element_status(filename,'node',node,'ran')
    except subprocess.CalledProcessError:
        edit_element_status(filename,'node',node,'fail')

def parse_arguments():
    parser = argparse.ArgumentParser(description="Run a node's associated command.")
    parser.add_argument("filename", type=str, help="Path to the input GraphML file.")
    parser.add_argument("node", type=str, help="Node to execute.")
    parser.add_argument("--prefix", '-p', default='bash -c', required=False, type=str, help="Prefix for command execution.")
    return parser.parse_args()

if __name__ == '__main__':
    args = parse_arguments()
    run_node(args.filename, args.node, args.prefix)
