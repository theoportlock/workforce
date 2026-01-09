import networkx as nx
import os
import sys
import tempfile
import logging
import uuid
import time
from contextlib import contextmanager

log = logging.getLogger(__name__)

# Cross-platform file locking
if sys.platform == 'win32':
    import msvcrt
    
    @contextmanager
    def file_lock(filepath, timeout=10):
        """Windows file locking using msvcrt."""
        lock_file = filepath + '.lock'
        start_time = time.time()
        
        while True:
            try:
                # Try to create lock file exclusively
                fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                try:
                    # Lock the file descriptor
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                    yield
                    break
                finally:
                    # Unlock and remove lock file
                    try:
                        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                    except:
                        pass
                    os.close(fd)
                    try:
                        os.unlink(lock_file)
                    except:
                        pass
            except (OSError, IOError):
                # Lock file exists or locking failed
                if time.time() - start_time > timeout:
                    raise TimeoutError(f"Could not acquire lock on {filepath} after {timeout}s")
                time.sleep(0.1)
else:
    import fcntl
    
    @contextmanager
    def file_lock(filepath, timeout=10):
        """Unix file locking using fcntl."""
        lock_file = filepath + '.lock'
        start_time = time.time()
        
        while True:
            try:
                fd = os.open(lock_file, os.O_CREAT | os.O_RDWR, 0o644)
                try:
                    # Try non-blocking lock first
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    yield
                    break
                except (IOError, OSError):
                    # Lock is held by another process
                    if time.time() - start_time > timeout:
                        raise TimeoutError(f"Could not acquire lock on {filepath} after {timeout}s")
                    time.sleep(0.1)
                finally:
                    try:
                        fcntl.flock(fd, fcntl.LOCK_UN)
                    except:
                        pass
                    os.close(fd)
            except Exception as e:
                if time.time() - start_time > timeout:
                    raise TimeoutError(f"Could not acquire lock on {filepath}: {e}")
                time.sleep(0.1)

def load_graph(path: str) -> nx.DiGraph:
    """Load graph from file with file locking to prevent concurrent access issues."""
    if not os.path.exists(path):
        # Create new graph file with lock
        with file_lock(path):
            # Double-check after acquiring lock
            if not os.path.exists(path):
                G = nx.DiGraph()
                nx.write_graphml(G, path)
                return G
    
    # Read with lock protection
    with file_lock(path):
        G = nx.read_graphml(path)
        return nx.DiGraph(G)

def save_graph(G: nx.DiGraph, path: str):
    """Save graph to file atomically with file locking.
    
    Uses temporary file + os.replace for atomic write,
    protected by file lock to prevent concurrent writes.
    """
    with file_lock(path):
        dirpath = os.path.dirname(path)
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
