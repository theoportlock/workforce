#!/usr/bin/env python
import os
import time
import subprocess
import networkx as nx
from filelock import FileLock
import argparse

def schedule_tasks(filename):
    with FileLock(f"{filename}.lock"):
        G = nx.read_graphml(filename)
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
                    if G.in_degree(node) > 0 and  # Exclude nodes with in-degree of 0
                    all(edge_status.get((u, node)) == 'to_run' for u, _ in G.in_edges(node))}
                if ready_nodes:
                    nx.set_node_attributes(G, {node: 'run' for node in ready_nodes}, 'status')
                    reverse_edges = [(u, v) for node in ready_nodes for u, v in G.in_edges(node)]
                    [G.edges[edge].pop('status', None) for edge in reverse_edges]
        nx.write_graphml(G, filename)
        if not nx.get_node_attributes(G, "status"):
            return 'complete'

def parse_arguments():
    parser = argparse.ArgumentParser(description="Schedule tasks with a GraphML file")
    parser.add_argument("filename", type=str, help="Path to the input GraphML file.")
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_arguments()
    schedule_tasks(args.filename)

