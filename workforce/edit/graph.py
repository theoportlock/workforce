import networkx as nx
import os
import tempfile
import logging
import uuid

log = logging.getLogger(__name__)

def load_graph(path: str) -> nx.DiGraph:
    """Load graph from file.
    
    Note: Concurrency safety is provided by the server's single-threaded queue worker
    (see workforce/server/queue.py), which serializes all graph mutations. Direct file
    access is safe because the singleton server architecture prevents concurrent writes.
    """
    if not os.path.exists(path):
        # Create new empty graph
        G = nx.DiGraph()
        nx.write_graphml(G, path)
        return G
    
    # Read existing graph
    G = nx.read_graphml(path)
    return nx.DiGraph(G)

def save_graph(G: nx.DiGraph, path: str):
    """Save graph to file atomically.
    
    Uses temporary file + os.replace for atomic write, which handles crash safety.
    Concurrency safety is provided by the server's single-threaded queue worker.
    """
    dirpath = os.path.dirname(path) if os.path.dirname(path) else '.'
    with tempfile.NamedTemporaryFile(dir=dirpath, delete=False, mode='wb') as tmp:
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

def edit_node_positions_in_graph(path, positions):
    """Batch update positions for multiple nodes.
    
    Args:
        path: Path to graph file
        positions: List of dicts with keys: node_id, x, y
        
    Returns:
        Dict with status and count of updated nodes
    """
    G = load_graph(path)
    updated = 0
    missing = []
    
    for pos in positions:
        node_id = pos.get("node_id")
        x = pos.get("x")
        y = pos.get("y")
        
        if node_id in G:
            G.nodes[node_id]["x"] = str(x)
            G.nodes[node_id]["y"] = str(y)
            updated += 1
        else:
            missing.append(node_id)
    
    save_graph(G, path)
    log.info(f"Batch updated positions for {updated} nodes in graph: {path}")
    
    result = {"status": "updated", "count": updated}
    if missing:
        result["missing_nodes"] = missing
    return result

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
    """DEPRECATED: Use save_node_execution_data_in_graph instead."""
    G = load_graph(path)
    if node_id not in G:
        return {"error": "Node not found"}
    G.nodes[node_id]["log"] = log
    save_graph(G, path)
    return {"status": "updated"}

def save_node_execution_data_in_graph(path, node_id, command, stdout, stderr, pid, error_code):
    """Save execution data as separate node attributes (all as strings).
    
    Args:
        path: Path to graph file
        node_id: Node ID to update
        command: The command that was executed (string)
        stdout: Standard output from command (string)
        stderr: Standard error from command (string)
        pid: Process ID (string representation of int)
        error_code: Exit code (string representation of int)
        
    Returns:
        Dict with status
    """
    G = load_graph(path)
    if node_id not in G:
        return {"error": "Node not found"}
    
    G.nodes[node_id]["command"] = str(command) if command else ""
    G.nodes[node_id]["stdout"] = str(stdout) if stdout else ""
    G.nodes[node_id]["stderr"] = str(stderr) if stderr else ""
    G.nodes[node_id]["pid"] = str(pid) if pid else ""
    G.nodes[node_id]["error_code"] = str(error_code) if error_code else ""
    
    save_graph(G, path)
    log.info(f"Saved execution data for node {node_id} in graph: {path}")
    return {"status": "updated"}

def edit_statuses_in_graph(path, updates):
    """Batch update statuses for multiple elements (nodes/edges).
    
    Args:
        path: Path to graph file
        updates: List of dicts with keys: element_type, element_id, value
        
    Returns:
        Dict with status and count of updated elements
        
    Raises:
        Returns error if any element is not found (fail-fast)
    """
    G = load_graph(path)
    
    # Validate all elements exist first (fail-fast)
    for update in updates:
        element_type = update.get("element_type")
        element_id = update.get("element_id")
        
        if element_type == "node":
            if element_id not in G:
                return {"error": f"Node not found: {element_id}"}
        elif element_type == "edge":
            found = False
            for u, v, data in G.edges(data=True):
                if str(data.get("id")) == str(element_id):
                    found = True
                    break
            if not found:
                return {"error": f"Edge not found: {element_id}"}
        else:
            return {"error": f"Invalid element_type: {element_type}"}
    
    # All elements exist, perform updates
    updated = 0
    for update in updates:
        element_type = update.get("element_type")
        element_id = update.get("element_id")
        value = update.get("value", "")
        
        if element_type == "node":
            G.nodes[element_id]["status"] = value
            updated += 1
        elif element_type == "edge":
            for u, v, data in G.edges(data=True):
                if str(data.get("id")) == str(element_id):
                    data["status"] = value
                    updated += 1
                    break
    
    save_graph(G, path)
    log.info(f"Batch updated statuses for {updated} elements in graph: {path}")
    return {"status": "updated", "count": updated}

def remove_node_logs_in_graph(path, node_ids):
    """Remove execution logs from multiple nodes.
    
    Args:
        path: Path to graph file
        node_ids: List of node IDs to clear logs from
        
    Returns:
        Dict with status and count of cleared nodes
        
    Raises:
        Returns error if any node is not found (fail-fast)
    """
    G = load_graph(path)
    
    # Validate all nodes exist first (fail-fast)
    for node_id in node_ids:
        if node_id not in G:
            return {"error": f"Node not found: {node_id}"}
    
    # All nodes exist, clear logs
    log_fields = ["log", "command", "stdout", "stderr", "pid", "error_code"]
    cleared = 0
    
    for node_id in node_ids:
        for field in log_fields:
            if field in G.nodes[node_id]:
                del G.nodes[node_id][field]
        cleared += 1
    
    save_graph(G, path)
    log.info(f"Cleared logs from {cleared} nodes in graph: {path}")
    return {"status": "cleared", "count": cleared}
