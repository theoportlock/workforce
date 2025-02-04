#!/usr/bin/env python
import os
import time
import subprocess
import networkx as nx
from filelock import FileLock
import argparse

def read_graph(filename):
    return nx.read_graphml(filename)

def write_graph(G, filename):
    nx.write_graphml(G, filename)

def get_status(G):
    node_status = nx.get_node_attributes(G, "status")
    edge_status = nx.get_edge_attributes(G, "status")
    return node_status, edge_status

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
    schedule_tasks(filename, lock)


