#!/usr/bin/env python
import os
import time
import subprocess
import networkx as nx
from multiprocessing import Process
from filelock import FileLock
import argparse

# WRITE FUNCTION TO BE CALLED BY CLI
# UPDATE NETWORK (NODE/EDGE STATUS) - FOR LOOPS

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

def schedule_tasks(filename, lock):
    """Set the run status for nodes that are ready to execute."""
    with lock:
        G = read_graph(filename)
        node_status = nx.get_node_attributes(G, 'status')
        edge_status = nx.get_edge_attributes(G, 'status')
        node_updates, edge_updates = {}, {}
        if not node_status:
            node_updates |= {node:'run' for node, degree in G.in_degree() if degree == 0}
        else:
# 1. for all ran nodes - mark all forward edges to_run and remove run status
            ran_nodes = [node for node, status in node_status.items() if status == 'ran']
            forward_edges = [list(G.out_edges(node)) for node in ran_nodes]
# 2. run all nodes that have all target edges set to to_run and remove to_run on edges
            successor_nodes = [list(G.successors(node)) for node in ran_nodes]
            unique_nodes = set(node for sublist in successor_nodes for node in sublist)
            to_run = {node: 'to_run' for node in unique_nodes}
            nx.set_node_attributes(G, to_run, 'status')
            # Run nodes that are marked to_run if all predecessors are ran
            filtered_nodes = {
                node for node in unique_nodes
                if all(pred in ran_nodes for pred in G.predecessors(node))
            }
            run = {node: 'run' for node in filtered_nodes}
            nx.set_node_attributes(G, run, 'status')
            #the ran nodes that have no successors marked as to_run, delete attr
            filtered_nodes = {
                node for node in ran_nodes
                if any(succ == 'to_run' in ran_nodes for succ in G.successors(node))
            }
            predecessor_nodes = [list(G.predecessors(node)) for node in filtered_nodes]
            remove_nodes = ran_nodes if not predecessor_nodes else set(node for sublist in predecessor_nodes for node in sublist)
            [G.nodes[node].pop('status', None) for node in remove_nodes]

            nx.set_node_attributes(G, node_updates, 'status')
            nx.set_edge_attributes(G, edge_updates, 'status')

        write_graph(G, filename)
        run_complete = not bool(nx.get_node_attributes(G, 'status'))
    return run_complete

def run_tasks(filename, lock):
    with lock:
        G = read_graph(filename)
        nodes_to_run = [
            node for node, status in nx.get_node_attributes(G, 'status').items() 
            if status == 'run'
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
    tasks = [schedule_tasks, run_tasks]
    processes = [Process(target=task, args=(filename, lock)) for task in tasks]
    [p.start() for p in processes]
    #[p.join() for p in processes]
    os.remove(f"{filename}.lock")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process graph nodes with dependencies.")
    parser.add_argument("filename", help="Path to the GraphML file")
    args = parser.parse_args()
    
    worker(args.filename)

