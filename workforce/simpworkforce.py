#!/usr/bin/env python
import os
import subprocess
import networkx as nx
from filelock import FileLock
import multiprocessing
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
        command = G.nodes[node].get('label', '')
        subprocess.run(command, shell=True, check=True)
        status = 'completed'
    except subprocess.CalledProcessError:
        status = 'failed'

    with lock:
        G = read_graph(filename)
        update_node_status(G, node, status)
        write_graph(G, filename)

    schedule_tasks(filename, lock)

def schedule_tasks(filename, lock):
    with lock:
        G = read_graph(filename)
        node_status = nx.get_node_attributes(G, 'status')

        # Identify nodes ready to run (all predecessors completed)
        ready_nodes = [
            node for node in G.nodes
            if node_status.get(node) is None and
            all(node_status.get(pred) == 'completed' for pred in G.predecessors(node))
        ]

        for node in ready_nodes:
            update_node_status(G, node, 'ready')

        write_graph(G, filename)

    run_tasks(filename, lock)

def run_tasks(filename, lock):
    with lock:
        G = read_graph(filename)
        ready_nodes = [
            node for node, status in nx.get_node_attributes(G, 'status').items()
            if status == 'ready'
        ]

    processes = [
        multiprocessing.Process(target=execute_node, args=(filename, node, lock))
        for node in ready_nodes
    ]

    for process in processes:
        process.start()

    for process in processes:
        process.join()

def worker(filename):
    lock = FileLock(f"{filename}.lock")
    schedule_tasks(filename, lock)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process graph nodes with dependencies.")
    parser.add_argument("filename", help="Path to the GraphML file")
    args = parser.parse_args()
    
    worker(args.filename)

