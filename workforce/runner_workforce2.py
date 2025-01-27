#!/usr/bin/env python
import os
import time
import subprocess
import networkx as nx
from filelock import FileLock
import argparse

def read_graph(filename):
    return nx.read_graphml(filename)

def write_graph(G, filename):
    with open(filename, 'w', newline='\n') as file:
        nx.write_graphml(G, file)
        file.write('\n')

def get_status(G):
    node_status = nx.get_node_attributes(G, "status")
    edge_status = nx.get_edge_attributes(G, "status")
    return node_status, edge_status

def schedule_tasks(filename, lock):
    with lock:
        G = read_graph(filename)
        node_status, edge_status = get_status(G)
        if not node_status or edge_status:
            node_updates = {node:'run' for node, degree in G.in_degree() if degree == 0}
            nx.set_node_attributes(G, node_updates, 'status')
        else:
            ran_nodes = [node for node, status in node_status.items() if status == 'ran']
            forward_edges = [(u, v) for node in ran_nodes for u, v in G.out_edges(node)]
            edge_updates = {edge:'to_run' for edge in forward_edges}
            nx.set_edge_attributes(G, edge_updates, 'status')
            [G.nodes[node].pop('status', None) for node in ran_nodes]
            node_status, edge_status = get_status(G)
            target_nodes = [v for _, v in edge_status]
            unique_nodes = set(node for node in target_nodes)
            run = {node: 'run' for node in unique_nodes}
            nx.set_node_attributes(G, run, 'status')
            reverse_edges = [(u, v) for node in run for u, v in G.in_edges(node)]
            [G.edges[edge].pop('status', None) for edge in reverse_edges]
        write_graph(G, filename)

def parse_arguments():
    parser = argparse.ArgumentParser(description="Schedule tasks with a graph.")
    parser.add_argument("filename", type=str, help="Path to the input graph file.")
    parser.add_argument("--prefix", type=str, help="Prefix for node excecution")
    parser.add_argument("--suffix", type=str, help="Suffix for node excecution")
    return parser.parse_args()

def update_filename(filename):
    G = read_graph(filename)
    filename = f"{os.getpid()}_{os.path.basename(filename)}"
    write_graph(G, filename)
    return filename

def worker(filename):
    filename = update_filename(filename)
    lock = FileLock(f"{filename}.lock")
    schedule_tasks(filename, lock)

if __name__ == "__main__":
    args = parse_arguments()
    worker(args.filename)

