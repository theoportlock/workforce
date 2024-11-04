#!/usr/bin/env python
import os
import time
import subprocess
import networkx as nx
from multiprocessing import Process
from filelock import FileLock
import argparse

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
    """Execute a node's label as a command and update its status."""
    with lock:
        G = read_graph(filename)
    update_node_status(filename, node, 'running', lock)
    try:
        subprocess.run(G.nodes[node].get('label'), shell=True, check=True)
        update_node_status(filename, node, 'ran', lock)
    except subprocess.CalledProcessError:
        update_node_status(filename, node, 'fail', lock)

# FIX THIS
def schedule_nodes(filename, lock):
    """Set the run status for nodes that are ready to execute."""
    with lock:
        G = read_graph(filename)
        nodes_with_status = nx.get_node_attributes(G, 'status')
        for node in G.nodes:
            predecessors = list(G.predecessors(node))
            if not predecessors:
                G.nodes[node]['status'] = 'to_run'
            elif all(G.nodes[pred].get('status') == 'ran' for pred in predecessors):
                G.nodes[node]['status'] = 'to_run'
                [del G.nodes[pred].get('status') == 'ran' for pred in predecessors]
        write_graph(G, filename)
    remaining_nodes = [status for status in nx.get_node_attributes(G, 'status').values()]
    return not any(status == 'to_run' for status in remaining_nodes) or 'fail' in remaining_nodes
def schedule_nodes(filename, lock):
    """Set the run status for nodes that are ready to execute."""
    with lock:
        G = read_graph(filename)
        # Set all first runners to run
        nodes_with_status = nx.get_node_attributes(G, 'status')
        if not nodes_with_status:
            to_run = {node: 'to_run' for node, degree in G.in_degree() if degree == 0}
            nx.set_node_attributes(G, to_run, 'status')
        else:
            ran_nodes = [node for node, status in nodes_with_status.items() if status == 'ran']
            successor_nodes = (G.successors(node) for node in ran_nodes)
            successors_that_have_all_ran_nodes = 
            for node in ran_nodes:
                for successor in G.successors(node):
                    if G.nodes[successor].get('status') != 'ran':
                        G.nodes[successor]['status'] = 'to_run'
        write_graph(G, filename)
    return not bool(nx.get_node_attributes(G, 'status'))

def run_tasks(filename, lock):
    with lock:
        G = read_graph(filename)
        nodes_to_run = [
            node for node, status in nx.get_node_attributes(G, 'status').items() 
            if status == 'to_run'
        ]
    processes = []
    for node in nodes_to_run:
        p = Process(target=execute_node, args=(filename, node, lock))
        processes.append(p)
        p.start()
    for p in processes:
        p.join()

def worker(filename):
    lock = FileLock(f"{filename}.lock")
    while True:
        if schedule_nodes(filename, lock):  # Break if no more tasks or a failure is detected
            os.remove(f"{filename}.lock")
            break
        run_tasks(filename, lock)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process graph nodes with dependencies.")
    parser.add_argument("filename", help="Path to the GraphML file")
    args = parser.parse_args()
    
    worker(args.filename)

