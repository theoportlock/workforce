import networkx as nx
import os
import tempfile
import logging
import uuid

log = logging.getLogger(__name__)

def load_graph(path: str) -> nx.DiGraph:
    if not os.path.exists(path):
        G = nx.DiGraph()
        nx.write_graphml(G, path)
        return G
    G = nx.read_graphml(path)
    return nx.DiGraph(G)

def save_graph(G: nx.DiGraph, path: str):
    dirpath = os.path.dirname(path)
    with tempfile.NamedTemporaryFile(dir=dirpath, delete=False) as tmp:
        tmppath = tmp.name
    nx.write_graphml(G, tmppath)
    os.replace(tmppath, path)

def add_node_to_graph(path, label, x=0.0, y=0.0, status=""):
    G = load_graph(path)
    node_id = str(uuid.uuid4())
    G.add_node(node_id, label=label, x=str(x), y=str(y), status=status)
    save_graph(G, path)
    log.info(f"Added node {node_id} to graph: {path}")
    return {"node_id": node_id}

def remove_node_from_graph(path, node_id):
    G = load_graph(path)
    if node_id in G:
        G.remove_node(node_id)
        save_graph(G, path)
        log.info(f"Removed node {node_id} from graph: {path}")
        return {"status": "removed"}
    return {"error": "Node not found"}

def add_edge_to_graph(path, source, target):
    G = load_graph(path)
    if source not in G or target not in G:
        return {"error": "Both source and target must exist"}
    edge_id = str(uuid.uuid4())
    G.add_edge(source, target, id=edge_id)
    save_graph(G, path)
    log.info(f"Added edge {edge_id} ({source} -> {target}) to graph: {path}")
    return {"edge_id": edge_id}


def remove_edge_from_graph(path, source, target):
    G = load_graph(path)
    if G.has_edge(source, target):
        G.remove_edge(source, target)
        save_graph(G, path)
        log.info(f"Removed edge ({source} -> {target}) from graph: {path}")
        return {"status": "removed"}
    return {"error": "Edge not found"}

def edit_status_in_graph(path, element_type, element_id, value):
    log.info(f"Updating status of {element_id} to {value}")
    G = load_graph(path)

    if element_type == "node":
        if element_id in G:
            G.nodes[element_id]["status"] = value
            save_graph(G, path)
            log.info(f"Set node {element_id} status to '{value}' in graph: {path}")
            return {"status": "updated"}
        return {"error": "Node not found"}

    if element_type == "edge":
        for u, v, data in G.edges(data=True):
            if str(data.get("id")) == str(element_id):
                data["status"] = value
                save_graph(G, path)
                log.info(f"Set edge {element_id} status to '{value}' in graph: {path}")
                return {"status": "updated"}
        return {"error": "Edge not found"}

    return {"error": "element_type must be node or edge"}

def edit_node_position_in_graph(path, node_id, x, y):
    G = load_graph(path)
    if node_id not in G:
        return {"error": "Node not found"}
    G.nodes[node_id]["x"] = str(x)
    G.nodes[node_id]["y"] = str(y)
    save_graph(G, path)
    return {"status": "updated"}

def edit_wrapper_in_graph(path, wrapper):
    G = load_graph(path)
    if wrapper is not None:
        G.graph['wrapper'] = wrapper
    save_graph(G, path)
    return {"status": "updated"}

def edit_node_label_in_graph(path, node_id, label):
    G = load_graph(path)
    if node_id not in G:
        return {"error": "Node not found"}
    G.nodes[node_id]["label"] = label
    save_graph(G, path)
    return {"status": "updated"}

def save_node_log_in_graph(path, node_id, log):
    G = load_graph(path)
    if node_id not in G:
        return {"error": "Node not found"}
    G.nodes[node_id]["log"] = log
    save_graph(G, path)
    return {"status": "updated"}
