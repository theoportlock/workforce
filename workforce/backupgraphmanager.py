import networkx as nx
import multiprocessing
import time
import json

GRAPHML_FILE = "graph.graphml"

def load_graph():
    try:
        return nx.read_graphml(GRAPHML_FILE)
    except FileNotFoundError:
        return nx.Graph()

def save_graph(G):
    nx.write_graphml(G, GRAPHML_FILE)

def graph_worker(task_queue, result_queue):
    """Process tasks related to GraphML file management"""
    G = load_graph()

    while True:
        task = task_queue.get()
        if task is None:
            break  # Exit the worker

        action = task["action"]
        if action == "read":
            result_queue.put(nx.node_link_data(G))  # Send graph data
        elif action == "update":
            updates = task["updates"]  # List of updates (e.g., adding nodes/edges)
            for update in updates:
                if update["type"] == "add_node":
                    G.add_node(update["node"], **update["attributes"])
                elif update["type"] == "add_edge":
                    G.add_edge(update["source"], update["target"], **update["attributes"])
            save_graph(G)
            result_queue.put({"status": "updated"})

if __name__ == "__main__":
    task_queue = multiprocessing.Queue()
    result_queue = multiprocessing.Queue()

    worker = multiprocessing.Process(target=graph_worker, args=(task_queue, result_queue))
    worker.start()

    # Example usage (replace with your processes' logic)
    task_queue.put({"action": "read"})
    time.sleep(1)  # Give the worker time to process
    print("Graph Data:", result_queue.get())

    # Update example
    task_queue.put({
        "action": "update",
        "updates": [{"type": "add_node", "node": "A", "attributes": {"label": "Node A"}}]
    })
    time.sleep(1)
    print(result_queue.get())

    # Stop the worker
    task_queue.put(None)
    worker.join()

