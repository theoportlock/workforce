#!/usr/bin/env python

from workforce_schedule import schedule_tasks
from workforce_edit_element import edit_element_status
import argparse
import networkx as nx
import subprocess
import time

def parse_arguments():
    parser = argparse.ArgumentParser(description="Schedule tasks with a graph.")
    parser.add_argument("filename", help="Path to the input GraphML file.")
    parser.add_argument("--prefix", '-p', default='bash -c', type=str, help="Prefix for node execution")
    parser.add_argument("--run_task", action="store_true", help="Run a single task and exit")
    parser.add_argument("--speed", type=float, default=2, help="Seconds inbetween job submission")
    return parser.parse_args()

def run_tasks(filename, prefix='bash -c'):
    G = nx.read_graphml(filename)
    node_status = nx.get_node_attributes(G, "status")
    run_nodes = {node for node, status in node_status.items() if status == 'run'}
    
    if run_nodes:
        node_to_run = run_nodes.pop()
        edit_element_status(filename,'node',node_to_run,'running')
        subprocess.Popen(["workforce_run_node.py", filename, node_to_run, "-p", prefix])

def worker(filename, prefix='bash -c', speed=2):
    while schedule_tasks(filename) != 'complete':
        run_tasks(filename, prefix)
        time.sleep(speed)

if __name__ == "__main__":
    args = parse_arguments()

    if args.run_task:
        run_tasks(args.filename, args.prefix)
    else:
        worker(args.filename, args.prefix, args.speed)
