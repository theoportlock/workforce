#!/usr/bin/env python
import os
import time
import subprocess
import networkx as nx
import multiprocessing
from filelock import FileLock
import argparse
from concurrent.futures import ProcessPoolExecutor

def read_graph(filename):
    return nx.read_graphml(filename)

def write_graph(G, filename):
    nx.write_graphml(G, filename)

def update_node_status(filename, node, status, lock):
    with lock:
        G = read_graph(filename)
        nx.set_node_attributes(G, {node: status}, 'status')
        write_graph(G, filename)

def execute_node(filename, node, lock):
    with lock:
        G = read_graph(filename)
    update_node_status(filename, node, 'running', lock)
    try:
        subprocess.run(G.nodes[node].get('label'), shell=True, check=True)
        update_node_status(filename, node, 'ran', lock)
    except subprocess.CalledProcessError:
        update_node_status(filename, node, 'fail', lock)

def schedule_tasks(filename, lock):
    with lock:
        G = read_graph(filename)
        node_status = nx.get_node_attributes(G, 'status')
        edge_status = nx.get_edge_attributes(G, 'status')
        if not node_status or edge_status:
            node_updates = {node: 'run' for node, degree in G.in_degree() if degree == 0}
            nx.set_node_attributes(G, node_updates, 'status')
        else:
            ran_nodes = [node for node, status in node_status.items() if status == 'ran']
            forward_edges = [(u, v) for node in ran_nodes for u, v in G.out_edges(node)]
            edge_updates = {edge: 'to_run' for edge in forward_edges}
            nx.set_edge_attributes(G, edge_updates, 'status')
            [G.nodes[node].pop('status', None) for node in ran_nodes]
            edge_status = nx.get_edge_attributes(G, 'status')
            target_nodes = [v for _, v in edge_status]
            unique_nodes = set(node for node in target_nodes)
            run = {node: 'run' for node in unique_nodes}
            nx.set_node_attributes(G, run, 'status')
            reverse_edges = [(u, v) for node in run for u, v in G.in_edges(node)]
            [G.edges[edge].pop('status', None) for edge in reverse_edges]
        write_graph(G, filename)
        run_complete = not bool(nx.get_node_attributes(G, 'status'))
    return run_complete

def run_tasks(filename, lock):
    with lock:
        G = read_graph(filename)
        nodes_to_run = [node for node, status in nx.get_node_attributes(G, 'status').items() if status == 'run']
    
    # Using ProcessPoolExecutor to manage parallel execution
    with ProcessPoolExecutor() as executor:
        # Start processes and wait for them to finish
        futures = [executor.submit(execute_node, filename, node, lock) for node in nodes_to_run]
        for future in futures:
            future.result()  # Wait for each task to complete

def worker(filename):
    # Use fork to handle parallelism on Unix-based systems
    multiprocessing.set_start_method('fork')
    lock = FileLock(f"{filename}.lock")
    
    while True:
        completed = schedule_tasks(filename, lock)
        if completed:
            os.remove(filename + '.lock')
            break
        run_tasks(filename, lock)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process graph nodes with dependencies.")
    parser.add_argument("filename", help="Path to the GraphML file")
    args = parser.parse_args()
    
    worker(args.filename)
