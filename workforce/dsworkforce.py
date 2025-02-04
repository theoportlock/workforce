#!/usr/bin/env python
import os
import time
import subprocess
import networkx as nx
import multiprocessing
from filelock import FileLock
import argparse

def read_graph(filename):
    return nx.read_graphml(filename)

def write_graph(G, filename):
    nx.write_graphml(G, filename)

def update_node_status(G, node, status):
    nx.set_node_attributes(G, {node: status}, 'status')

def execute_node(filename, node, lock):
    with lock:
        G = read_graph(filename)
        update_node_status(G, node, 'running')
        write_graph(G, filename)
    
    try:
        subprocess.run(G.nodes[node].get('label'), shell=True, check=True)
        with lock:
            G = read_graph(filename)
            update_node_status(G, node, 'ran')
            write_graph(G, filename)
    except subprocess.CalledProcessError:
        with lock:
            G = read_graph(filename)
            update_node_status(G, node, 'fail')
            write_graph(G, filename)
    
    schedule_tasks(filename, lock)

def schedule_tasks(filename, lock):
    with lock:
        G = read_graph(filename)
        node_status = nx.get_node_attributes(G, 'status')
        edge_status = nx.get_edge_attributes(G, 'status')
        
        if not node_status or not edge_status:
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
            unique_nodes = set(target_nodes)
            run = {node: 'run' for node in unique_nodes}
            nx.set_node_attributes(G, run, 'status')
            reverse_edges = [(u, v) for node in run for u, v in G.in_edges(node)]
            [G.edges[edge].pop('status', None) for edge in reverse_edges]
        
        write_graph(G, filename)
        
        if bool(nx.get_node_attributes(G, 'status')):
            run_tasks(filename, lock)
        else:
            os.remove(filename + '.lock')
            os.remove(filename)

def run_tasks(filename, lock):
    with lock:
        G = read_graph(filename)
        nodes_to_run = [node for node, status in nx.get_node_attributes(G, 'status').items() if status == 'run']
    
    for node in nodes_to_run:
        multiprocessing.Process(target=execute_node, args=(filename, node, lock)).start()

def worker(filename):
    multiprocessing.set_start_method('fork')
    G = read_graph(filename)
    filename = f"{os.getpid()}_{os.path.basename(filename)}"
    write_graph(G, filename)
    lock = FileLock(f"{filename}.lock", thread_local=False)
    schedule_tasks(filename, lock)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process graph nodes with dependencies.")
    parser.add_argument("filename", help="Path to the GraphML file")
    args = parser.parse_args()
    
    worker(args.filename)
