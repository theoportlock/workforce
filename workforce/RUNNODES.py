#!/usr/bin/env python

from filelock import FileLock, Timeout
import sys
import subprocess
import networkx as nx
import time
import argparse

class GraphMLAtomic:
    """
    A context manager for atomically reading and writing a GraphML file.
    It uses a file lock to prevent race conditions when multiple processes
    try to modify the graph at the same time.
    """
    def __init__(self, filename):
        self.filename = filename
        self.lock = FileLock(f"{filename}.lock")

    def __enter__(self):
        """Acquire the lock and read the graph."""
        self.lock.acquire()
        try:
            self.G = nx.read_graphml(self.filename)
        except FileNotFoundError:
            # If the file doesn't exist, start with an empty graph.
            self.G = nx.DiGraph()
        return self.G

    def __exit__(self, exc_type, exc_value, traceback):
        """Write the graph and release the lock."""
        nx.write_graphml(self.G, self.filename)
        self.lock.release()

def edit_status(G, element_type, element_id, value):
    """
    Edits the 'status' attribute of a node or edge in the graph.
    
    Args:
        G (nx.DiGraph): The graph to modify.
        element_type (str): The type of element, either 'node' or 'edge'.
        element_id (str): The ID of the node or edge.
        value (str): The new status value.
    
    Returns:
        nx.DiGraph: The modified graph.
    """
    if element_type == 'node':
        if element_id not in G.nodes:
            raise ValueError(f"Node '{element_id}' not found in graph")
        G.nodes[element_id]['status'] = value
    elif element_type == 'edge':
        if element_id not in G.edges:
            raise ValueError(f"Edge '{element_id}' not found in graph")
        G.edges[element_id]['status'] = value
    return G

def run_tasks(filename, prefix='bash -c ', suffix=''):
    """
    A single-threaded function that checks for 'run' tasks and starts one.
    This is designed to be called repeatedly in a worker loop.
    
    Args:
        filename (str): The path to the GraphML file.
        prefix (str, optional): The command prefix. Defaults to 'bash -c '.
        suffix (str, optional): The command suffix. Defaults to ''.
    """
    with GraphMLAtomic(filename) as G:
        node_status = nx.get_node_attributes(G, "status")
        run_nodes = {node for node, status in node_status.items() if status == 'run'}
        if run_nodes:
            node = run_nodes.pop()
            G.nodes[node]['status'] = 'running'
        else:
            node = None
    if node:
        subprocess.Popen([
            sys.executable, "-m", "workforce", "run_node",
            filename, node, "-p", prefix, "-s", suffix
        ])

def worker(filename, prefix='bash -c ', suffix='', speed=0.5):
    """
    The main worker loop that initializes, schedules, and runs tasks
    until the entire pipeline is complete.
    
    Args:
        filename (str): The path to the GraphML file.
        prefix (str, optional): The command prefix. Defaults to 'bash -c '.
        suffix (str, optional): The command suffix. Defaults to ''.
        speed (float, optional): The sleep duration between checks. Defaults to 0.5.
    """
    initialize_pipeline(filename)
    status = ''
    while status != 'complete':
        time.sleep(speed)
        status = schedule_tasks(filename)
        run_tasks(filename, prefix, suffix)

def initialize_pipeline(filename):
    """
    Initializes the pipeline by setting the status of all failed nodes to 'run'
    and setting the status of initial nodes (with no incoming edges) to 'run'
    if no statuses are set.
    
    Args:
        filename (str): The path to the GraphML file.
    """
    with GraphMLAtomic(filename) as G:
        node_status = nx.get_node_attributes(G, "status")
        failed_nodes = {node for node, status in node_status.items() if status == 'fail'}
        if failed_nodes:
            nx.set_node_attributes(G, {node: 'run' for node in failed_nodes}, 'status')
        if not node_status:
            node_updates = {node: 'run' for node, degree in G.in_degree() if degree == 0}
            nx.set_node_attributes(G, node_updates, 'status')

def schedule_tasks(filename):
    """
    Updates the status of nodes based on completed tasks, preparing new tasks to run.
    
    Args:
        filename (str): The path to the GraphML file.
    
    Returns:
        str: The status of the pipeline ('complete' or '').
    """
    with GraphMLAtomic(filename) as G:
        node_status = nx.get_node_attributes(G, "status")
        ran_nodes = {node for node, status in node_status.items() if status == 'ran'}
        if ran_nodes:
            forward_edges = [(u, v) for node in ran_nodes for u, v in G.out_edges(node)]
            nx.set_edge_attributes(G, {edge: 'to_run' for edge in forward_edges}, 'status')
            [G.nodes[node].pop('status', None) for node in ran_nodes]
            edge_status = nx.get_edge_attributes(G, "status")
            ready_nodes = {
                node for node in G.nodes
                if G.in_degree(node) > 0 and
                all(edge_status.get((u, node)) == 'to_run' for u, _ in G.in_edges(node))
            }
            if ready_nodes:
                nx.set_node_attributes(G, {node: 'run' for node in ready_nodes}, 'status')
                reverse_edges = [(u, v) for node in ready_nodes for u, v in G.in_edges(node)]
                [G.edges[edge].pop('status', None) for edge in reverse_edges]
        node_status = nx.get_node_attributes(G, "status")
        active_nodes = {node for node, status in node_status.items() if status in ('run', 'ran', 'running')}
    if not active_nodes:
        return 'complete'
    return ''

def shell_quote_multiline(script: str) -> str:
    """
    Safely quote a multiline shell script for `bash -c '...'`.
    
    Args:
        script (str): The shell script to quote.
    
    Returns:
        str: The safely quoted script.
    """
    return script.replace("'", "'\\''")

def run_node(filename, node, prefix='bash -c ', suffix=''):
    """
    Runs a single node's command using subprocess.
    
    Args:
        filename (str): The path to the GraphML file.
        node (str): The ID of the node to run.
        prefix (str, optional): The command prefix. Defaults to 'bash -c '.
        suffix (str, optional): The command suffix. Defaults to ''.
    """
    with GraphMLAtomic(filename) as G:
        label = G.nodes[node].get('label', '')
        quoted_label = shell_quote_multiline(label)
        command = f"{prefix}{quoted_label}{suffix}".strip()
        print(f"Executing command for node '{node}': {command}")
        G.nodes[node]['status'] = 'running'
    try:
        # Use shell=True for the `bash -c` prefix to work as expected.
        subprocess.run(command, shell=True, check=True)
        with GraphMLAtomic(filename) as G:
            G.nodes[node]['status'] = 'ran'
            print(f"Node '{node}' completed successfully.")
    except subprocess.CalledProcessError as e:
        with GraphMLAtomic(filename) as G:
            G.nodes[node]['status'] = 'fail'
            print(f"Node '{node}' failed with exit code {e.returncode}.")

def safe_load(filename, lock_timeout=0.1):
    """
    Safely loads a graph from a file with a timeout on the lock.
    
    Args:
        filename (str): The path to the GraphML file.
        lock_timeout (float, optional): Timeout for acquiring the lock. Defaults to 0.1.
    
    Returns:
        nx.DiGraph or None: The graph object if the lock is acquired, otherwise None.
    """
    lock = FileLock(f"{filename}.lock")
    try:
        with lock.acquire(timeout=lock_timeout):
            return nx.read_graphml(filename)
    except Timeout:
        # Could not acquire the lock quickly; skip this update
        return None

# --- NEW FUNCTION FOR RUNNING A SUBSET OF NODES ---
def run_nodes_in_order(filename, nodes_to_run, prefix='bash -c ', suffix=''):
    """
    Runs a specific list of nodes by simulating the worker loop, respecting
    the dependencies as defined by the scheduling logic. This function
    does not assume a Directed Acyclic Graph (DAG) and handles cycles.

    Args:
        filename (str): The path to the GraphML file.
        nodes_to_run (list): A list of node IDs to execute.
        prefix (str, optional): The command prefix. Defaults to 'bash -c '.
        suffix (str, optional): The command suffix. Defaults to ''.
    """
    # Create a set for quick lookup of target nodes
    nodes_to_run_set = set(nodes_to_run)
    
    # Initialize the pipeline to prepare the initial runnable nodes
    initialize_pipeline(filename)

    # Keep track of which nodes from the target list have been successfully run
    completed_nodes = set()

    print(f"Starting execution of specified nodes: {nodes_to_run}")

    while completed_nodes != nodes_to_run_set:
        with GraphMLAtomic(filename) as G:
            node_status = nx.get_node_attributes(G, "status")
            # Get the set of all nodes that are currently ready to run
            runnable_nodes = {node for node, status in node_status.items() if status == 'run'}
            
            # Find the nodes that are both ready to run and in our target list
            runnable_target_nodes = sorted(list(runnable_nodes.intersection(nodes_to_run_set)))

            if not runnable_target_nodes and len(completed_nodes) < len(nodes_to_run_set):
                # If there are no runnable nodes from our target list, it might be a deadlock
                # or a dependency that isn't met.
                print("No more runnable nodes found among the specified list. Exiting.")
                print("Check if there are unfulfilled dependencies or a cycle within the target nodes.")
                break

            for node in runnable_target_nodes:
                print(f"\n--- Running node: {node} ---")
                run_node(filename, node, prefix, suffix)

                # After running, update the schedule to prepare next tasks
                schedule_tasks(filename)

        with GraphMLAtomic(filename) as G:
            node_status = nx.get_node_attributes(G, "status")
            # Update the set of completed nodes after each run
            completed_nodes.update({node for node, status in node_status.items() if status == 'ran' and node in nodes_to_run_set})

        # Add a small delay to prevent a tight loop
        time.sleep(0.5)

    print("\nAll specified nodes have been processed.")


# --- MAIN ENTRY POINT ---
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='A simple DAG workflow manager.')
    parser.add_argument('filename', help='The path to the GraphML file.')
    subparsers = parser.add_subparsers(dest='command', required=True)

    # Subparser for running the full pipeline
    parser_worker = subparsers.add_parser('worker', help='Run the full pipeline continuously.')
    parser_worker.add_argument('--prefix', default='bash -c ', help='Command prefix.')
    parser_worker.add_argument('--suffix', default='', help='Command suffix.')
    parser_worker.add_argument('--speed', type=float, default=0.5, help='Worker speed in seconds.')

    # Subparser for running a single node
    parser_run_node = subparsers.add_parser('run_node', help='Run a single node task.')
    parser_run_node.add_argument('node', help='The node ID to run.')
    parser_run_node.add_argument('--prefix', default='bash -c ', help='Command prefix.')
    parser_run_node.add_argument('--suffix', default='', help='Command suffix.')

    # Subparser for running a specific list of nodes in order
    parser_run_nodes = subparsers.add_parser('run_nodes', help='Run a specific list of nodes in topological order.')
    parser_run_nodes.add_argument('nodes', nargs='+', help='A list of node IDs to run.')
    parser_run_nodes.add_argument('--prefix', default='bash -c ', help='Command prefix.')
    parser_run_nodes.add_argument('--suffix', default='', help='Command suffix.')
    
    args = parser.parse_args()

    if args.command == 'worker':
        worker(args.filename, args.prefix, args.suffix, args.speed)
    elif args.command == 'run_node':
        run_node(args.filename, args.node, args.prefix, args.suffix)
    elif args.command == 'run_nodes':
        run_nodes_in_order(args.filename, args.nodes, args.prefix, args.suffix)

