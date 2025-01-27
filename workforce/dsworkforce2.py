#!/usr/bin/env python
import os
import subprocess
import networkx as nx
import multiprocessing
from filelock import FileLock
import argparse

def execute_node(filename, node, lock):
    with lock:
        G = nx.read_graphml(filename)
        G.nodes[node]['status'] = 'running'
        nx.write_graphml(G, filename)
    
    try:
        subprocess.run(G.nodes[node].get('label'), shell=True, check=True)
        with lock:
            G = nx.read_graphml(filename)
            G.nodes[node]['status'] = 'ran'
            nx.write_graphml(G, filename)
    except subprocess.CalledProcessError:
        with lock:
            G = nx.read_graphml(filename)
            G.nodes[node]['status'] = 'fail'
            nx.write_graphml(G, filename)
    
    schedule_tasks(filename, lock)

def schedule_tasks(filename, lock):
    with lock:
        G = nx.read_graphml(filename)
        node_status = nx.get_node_attributes(G, 'status')
        edge_status = nx.get_edge_attributes(G, 'status')
        
        # Fix logical condition for initial nodes
        if not node_status and not edge_status:
            for node, degree in G.in_degree():
                if degree == 0:
                    G.nodes[node]['status'] = 'run'
        else:
            # Update edges and subsequent nodes
            ran_nodes = [n for n, s in node_status.items() if s == 'ran']
            for node in ran_nodes:
                for _, v in G.out_edges(node):
                    G.edges[(node, v)]['status'] = 'to_run'
                del G.nodes[node]['status']
            
            # Find nodes with all predecessors completed
            for node in G.nodes():
                if all(G.edges[(u, node)].get('status') == 'to_run' 
                       for u in G.predecessors(node)):
                    G.nodes[node]['status'] = 'run'
            
            # Cleanup edge statuses
            for u, v in list(G.edges()):
                if 'status' in G.edges[(u, v)]:
                    del G.edges[(u, v)]['status']

        nx.write_graphml(G, filename)
        
        if nx.get_node_attributes(G, 'status'):
            run_tasks(filename, lock)
        else:
            os.remove(f"{filename}.lock")

def run_tasks(filename, lock):
    with lock:
        G = nx.read_graphml(filename)
        nodes_to_run = [n for n, s in nx.get_node_attributes(G, 'status').items() if s == 'run']
    
    for node in nodes_to_run:
        multiprocessing.Process(target=execute_node, args=(filename, node, lock)).start()

def worker(filename):
    multiprocessing.set_start_method('fork')
    lock = FileLock(f"{filename}.lock", thread_local=False)
    schedule_tasks(filename, lock)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process graph nodes with dependencies.")
    parser.add_argument("filename", help="Path to the GraphML file")
    args = parser.parse_args()
    worker(args.filename)
