#!/usr/bin/env python
import os
import subprocess
import networkx as nx
import multiprocessing
from filelock import FileLock, Timeout
import argparse
import tempfile

def execute_node(original_filename, node, lock):
    graph_file = original_filename
    lock_file = f"{original_filename}.lock"
    
    # Atomic read with lock
    with FileLock(lock_file, timeout=10):
        G = nx.read_graphml(graph_file)
        G.nodes[node]['status'] = 'running'
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
            nx.write_graphml(G, tmp.name)
            os.replace(tmp.name, graph_file)

    try:
        # Get command from original graph structure
        with FileLock(lock_file, timeout=10):
            G = nx.read_graphml(graph_file)
            cmd = G.nodes[node].get('label')
        
        # Execute command without lock
        subprocess.run(cmd, shell=True, check=True)
        
        # Update status after success
        with FileLock(lock_file, timeout=10):
            G = nx.read_graphml(graph_file)
            G.nodes[node]['status'] = 'ran'
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
                nx.write_graphml(G, tmp.name)
                os.replace(tmp.name, graph_file)
                
    except subprocess.CalledProcessError:
        with FileLock(lock_file, timeout=10):
            G = nx.read_graphml(graph_file)
            G.nodes[node]['status'] = 'fail'
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
                nx.write_graphml(G, tmp.name)
                os.replace(tmp.name, graph_file)
    
    schedule_tasks(original_filename)

def schedule_tasks(original_filename):
    graph_file = original_filename
    lock_file = f"{original_filename}.lock"
    
    with FileLock(lock_file, timeout=10):
        try:
            G = nx.read_graphml(graph_file)
        except Exception as e:
            print(f"Error reading graph: {e}")
            return

        node_status = nx.get_node_attributes(G, 'status')
        edge_status = nx.get_edge_attributes(G, 'status')

        # Initial setup
        if not node_status and not edge_status:
            roots = [n for n, d in G.in_degree() if d == 0]
            for node in roots:
                G.nodes[node]['status'] = 'run'
        else:
            # Find completed nodes and their dependents
            completed = [n for n, s in node_status.items() if s == 'ran']
            for node in completed:
                for successor in G.successors(node):
                    G.edges[node, successor]['status'] = 'completed'
                del G.nodes[node]['status']

            # Find nodes ready to run
            for node in G.nodes():
                predecessors = list(G.predecessors(node))
                if all(G.edges[p, node].get('status') == 'completed' for p in predecessors):
                    G.nodes[node]['status'] = 'run'

        # Atomic write
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
            nx.write_graphml(G, tmp.name)
            os.replace(tmp.name, graph_file)

        # Start new tasks if any
        nodes_to_run = [n for n, s in nx.get_node_attributes(G, 'status').items() if s == 'run']
        for node in nodes_to_run:
            p = multiprocessing.Process(target=execute_node, args=(original_filename, node))
            p.start()

def worker(filename):
    multiprocessing.set_start_method('fork')
    schedule_tasks(filename)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process graph nodes with dependencies.")
    parser.add_argument("filename", help="Path to the GraphML file")
    args = parser.parse_args()
    
    # Validate input file first
    try:
        G = nx.read_graphml(args.filename)
        nx.write_graphml(G, args.filename)  # Ensure valid format
    except Exception as e:
        print(f"Invalid input file: {e}")
        exit(1)
    
    worker(args.filename)
