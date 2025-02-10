#!/usr/bin/env python

from .schedule import schedule_tasks
from .edit_element import edit_element_status
from filelock import FileLock
import argparse
import networkx as nx
import subprocess
import time

def parse_arguments():
    parser = argparse.ArgumentParser(description="Schedule tasks with a graph.")
    parser.add_argument("filename", help="Path to the input GraphML file.")
    parser.add_argument("--prefix", '-p', default='bash -c', type=str, help="Prefix for node execution")
    parser.add_argument("--run_task", action="store_true", help="Run a single task and exit")
    parser.add_argument("--speed", type=float, default=0.5, help="Seconds inbetween job submission")
    return parser.parse_args()

def run_tasks(filename, prefix='bash -c'):
    lock = FileLock(f"{filename}.lock")
    with lock:
        G = nx.read_graphml(filename)
        node_status = nx.get_node_attributes(G, "status")
        run_nodes = {node for node, status in node_status.items() if status == 'run'}
        if run_nodes:
            node = run_nodes.pop()
            subprocess.Popen(["wf_run_node", filename, node, "-p", prefix])

def worker(filename, prefix='bash -c', speed=0.5):
    status = ''
    while status != 'complete':
        time.sleep(speed)
        status = schedule_tasks(filename)
        run_tasks(filename, prefix)

def main():
    args = parse_arguments()
    if args.run_task:
        run_tasks(args.filename, args.prefix)
    else:
        worker(args.filename, args.prefix, args.speed)

if __name__ == "__main__":
    main()
