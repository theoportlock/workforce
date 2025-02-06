#!/usr/bin/env python
from workforce_schedule import schedule_tasks
import argparse
import networkx as nx
import subprocess
import time

def parse_arguments():
    parser = argparse.ArgumentParser(description="Schedule tasks with a graph.")
    parser.add_argument("filename", type=str, help="Path to the input GraphML file.")
    parser.add_argument("--prefix", '-p', default='bash -c', type=str, help="Prefix for node execution")
    parser.add_argument("--run_task", action="store_true", help="Run tasks for the graph")
    return parser.parse_args()

def run_tasks(filename, prefix='bash -c'):
    G = nx.read_graphml(filename)
    node_status = nx.get_node_attributes(G, "status")
    run_nodes = {node for node, status in node_status.items() if status == 'run'}
    
    if run_nodes:
        node_to_run = run_nodes.pop()
        #subprocess.run(f"workforce_run_node.py {filename} {node_to_run} -p '{prefix}' &", shell=True)
        subprocess.Popen(f"workforce_run_node.py {filename} {node_to_run} -p '{prefix}' &", shell=True)

def worker(filename, prefix='bash -c'):
    while schedule_tasks(filename) != 'complete':
        run_tasks(filename, prefix)
        time.sleep(2)

if __name__ == "__main__":
    args = parse_arguments()

    if args.run_task:
        run_tasks(args.filename, args.prefix)
    else:
        worker(args.filename, args.prefix)
