import numpy as np
import sys
import os
import time
import subprocess
import pandas as pd
import networkx as nx
from multiprocessing import Process
from filelock import FileLock

def read_edges(filename):
    edges = pd.read_csv(filename, sep='\t', header=None)
    if edges.shape[1] == 2:
        edges.columns = ['source', 'target']
        edges['status'] = np.nan
    elif edges.shape[1] == 3:
        edges.columns = ['source', 'target', 'status']
    return edges

def save_edges(edges, filename):
    edges.to_csv(filename, sep='\t', index=False, header=None)

def set_edges(edges, node, column, status):
    edges.loc[edges[column] == node, 'status'] = status
    return edges

def to_nodes(edges):
    G = nx.from_pandas_edgelist(edges, create_using=nx.DiGraph())
    indegree = pd.DataFrame(G.in_degree(), columns=['nodes', 'in_degree']).set_index('nodes')
    outdegree = pd.DataFrame(G.out_degree(), columns=['nodes', 'out_degree']).set_index('nodes')
    run = edges.loc[edges['status'] == 'run'].groupby('target').count().status.to_frame('run')
    start = edges.loc[edges['status'] == 'start'].groupby('source').count().status.to_frame('start')
    nodes = pd.concat([indegree, outdegree, run, start], axis=1)
    nodes.loc[nodes['out_degree'] == nodes['start'], 'action'] = 'start'
    nodes.loc[nodes['in_degree'] == nodes['run'], 'action'] = 'run'
    return nodes

def ready_to_run(edges, node):
    df = edges.loc[edges.target == node, 'status']
    if not df.empty:
        if (df == 'ran').all():
            return True
    else:
        return False

def run(filename, node, action, lock):
    status = 'starting' if action == 'start' else 'running'
    column = 'source' if action == 'start' else 'target'
    with lock: save_edges(set_edges(read_edges(filename), node, column, status), filename)
    try:
        subprocess.run(node, shell=True, check=True)
        status = 'started' if action == 'start' else 'ran'
        with lock: save_edges(set_edges(read_edges(filename), node, column, status), filename)
    except subprocess.CalledProcessError:
        status = 'failed'
        with lock: save_edges(set_edges(read_edges(filename), node, column, status), filename)

def scheduler(filename, lock):
    edges = read_edges(filename)
    nodes = to_nodes(edges)
    if edges['status'].isnull().all():
        for node in nodes.loc[nodes.in_degree == 0].index.to_list():
            edges = set_edges(edges, node, 'source', 'start')
    else:
        edges = set_edges(edges, 'started', 'status', 'run')
        for node in nodes.index:
            if ready_to_run(edges, node):
                edges = set_edges(edges, node, 'source', 'run')
                edges = set_edges(edges, node, 'target', np.nan)
    with lock: save_edges(edges, filename)
    return True if edges['status'].isnull().all() else False

def runner(filename, lock):
    edges = read_edges(filename)
    nodes = to_nodes(edges).query('action == action')  # dropna
    for node in nodes.index:
        action = nodes.loc[node, 'action']
        Process(target=run, args=[filename, node, action, lock]).start()

def worker(filename=None):
    edges = read_edges(filename)
    filename = f"{os.getpid()}_{os.path.basename(filename)}"
    lock = FileLock(filename + '.lock')
    with lock: save_edges(edges, filename)
    while True:
        time.sleep(1)
        completed = scheduler(filename, lock)
        if completed:
            os.remove(filename + '.lock')
            os.remove(filename)
            break
        runner(filename, lock)

if __name__ == "__main__":
    filename = sys.argv[1]
    worker(filename)

