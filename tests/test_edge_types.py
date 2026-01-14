import uuid
import time
import networkx as nx
import pytest

from workforce.edit import graph as edit
from workforce.server.queue import start_graph_worker


def _add_node(G, label, status=""):
    node_id = str(uuid.uuid4())
    G.add_node(node_id, label=label, status=status, x="0", y="0")
    return node_id


def _save_graph(path, nodes, edges):
    G = nx.DiGraph()
    for node_id, label in nodes:
        G.add_node(node_id, label=label, status="", x="0", y="0")
    for src, tgt, edge_type in edges:
        G.add_edge(src, tgt, id=str(uuid.uuid4()), edge_type=edge_type)
    edit.save_graph(G, path)


def test_non_blocking_triggers_immediately(temp_graph_file, mock_server_context):
    """Non-blocking edge should trigger target as soon as source completes."""
    G = nx.DiGraph()
    a = _add_node(G, "echo A")
    b = _add_node(G, "echo B")
    G.add_edge(a, b, id=str(uuid.uuid4()), edge_type="non-blocking")
    edit.save_graph(G, temp_graph_file)

    ctx = mock_server_context
    start_graph_worker(ctx)
    time.sleep(0.05)

    run_id = str(uuid.uuid4())
    ctx.active_node_run[a] = run_id
    ctx.enqueue_status(temp_graph_file, "node", a, "ran", run_id)

    ctx.mod_queue.join()
    time.sleep(0.05)

    G2 = edit.load_graph(temp_graph_file)
    assert G2.nodes[b]["status"] == "run"


def test_non_blocking_allows_multiple_executions(temp_graph_file, mock_server_context):
    """Each non-blocking predecessor completion should trigger a new execution."""
    G = nx.DiGraph()
    a = _add_node(G, "echo A")
    b = _add_node(G, "echo B")
    c = _add_node(G, "echo C")
    G.add_edge(a, c, id=str(uuid.uuid4()), edge_type="non-blocking")
    G.add_edge(b, c, id=str(uuid.uuid4()), edge_type="non-blocking")
    edit.save_graph(G, temp_graph_file)

    ctx = mock_server_context
    start_graph_worker(ctx)
    time.sleep(0.05)

    run_id = str(uuid.uuid4())
    ctx.active_node_run[a] = run_id
    ctx.enqueue_status(temp_graph_file, "node", a, "ran", run_id)
    ctx.mod_queue.join()
    time.sleep(0.05)
    G1 = edit.load_graph(temp_graph_file)
    assert G1.nodes[c]["status"] == "run"

    # Mark C as completed to allow re-run
    ctx.active_node_run[c] = run_id
    ctx.enqueue_status(temp_graph_file, "node", c, "ran", run_id)
    ctx.mod_queue.join()

    ctx.active_node_run[b] = run_id
    ctx.enqueue_status(temp_graph_file, "node", b, "ran", run_id)
    ctx.mod_queue.join()
    time.sleep(0.05)

    G2 = edit.load_graph(temp_graph_file)
    assert G2.nodes[c]["status"] == "run"


def test_blocking_waits_for_all_predecessors(temp_graph_file, mock_server_context):
    """Blocking edges should gate execution until all blocking predecessors are ready."""
    nodes = []
    for label in ("echo A", "echo B", "echo C"):
        nodes.append(str(uuid.uuid4()))
    a, b, c = nodes
    edges = [
        (a, c, "blocking"),
        (b, c, "blocking"),
    ]
    _save_graph(temp_graph_file, [(n, lbl) for n, lbl in zip(nodes, ("echo A", "echo B", "echo C"))], edges)

    ctx = mock_server_context
    start_graph_worker(ctx)
    time.sleep(0.05)
    run_id = str(uuid.uuid4())

    ctx.active_node_run[a] = run_id
    ctx.enqueue_status(temp_graph_file, "node", a, "ran", run_id)
    ctx.mod_queue.join()
    time.sleep(0.05)
    assert edit.load_graph(temp_graph_file).nodes[c]["status"] == ""

    ctx.active_node_run[b] = run_id
    ctx.enqueue_status(temp_graph_file, "node", b, "ran", run_id)
    ctx.mod_queue.join()
    time.sleep(0.05)
    assert edit.load_graph(temp_graph_file).nodes[c]["status"] == "run"


def test_mixed_blocking_and_non_blocking(temp_graph_file, mock_server_context):
    """Non-blocking may run target early; blocking later retriggers."""
    G = nx.DiGraph()
    a = _add_node(G, "echo A")
    b = _add_node(G, "echo B")
    e = _add_node(G, "echo E")
    G.add_edge(a, e, id=str(uuid.uuid4()), edge_type="blocking")
    G.add_edge(b, e, id=str(uuid.uuid4()), edge_type="non-blocking")
    edit.save_graph(G, temp_graph_file)

    ctx = mock_server_context
    start_graph_worker(ctx)
    time.sleep(0.05)
    run_id = str(uuid.uuid4())

    ctx.active_node_run[b] = run_id
    ctx.enqueue_status(temp_graph_file, "node", b, "ran", run_id)
    ctx.mod_queue.join()
    time.sleep(0.05)
    assert edit.load_graph(temp_graph_file).nodes[e]["status"] == "run"

    ctx.active_node_run[e] = run_id
    ctx.enqueue_status(temp_graph_file, "node", e, "ran", run_id)
    ctx.mod_queue.join()

    ctx.active_node_run[a] = run_id
    ctx.enqueue_status(temp_graph_file, "node", a, "ran", run_id)
    ctx.mod_queue.join()
    time.sleep(0.05)
    assert edit.load_graph(temp_graph_file).nodes[e]["status"] == "run"


def test_subset_respects_non_blocking_edges(temp_graph_file, mock_server_context):
    """Subset runs should ignore edges whose endpoints are outside the subset."""
    G = nx.DiGraph()
    a = _add_node(G, "echo A")
    b = _add_node(G, "echo B")
    G.add_edge(a, b, id=str(uuid.uuid4()), edge_type="non-blocking")
    edit.save_graph(G, temp_graph_file)

    ctx = mock_server_context
    start_graph_worker(ctx)
    time.sleep(0.05)

    run_id = str(uuid.uuid4())
    ctx.active_runs[run_id] = {"nodes": {a}, "subset_only": True}
    ctx.active_node_run[a] = run_id
    ctx.enqueue_status(temp_graph_file, "node", a, "ran", run_id)

    ctx.mod_queue.join()
    time.sleep(0.05)
    assert edit.load_graph(temp_graph_file).nodes[b]["status"] == ""


def test_default_edge_type_is_blocking(temp_graph_file, mock_server_context):
    """Edges without edge_type default to blocking behavior."""
    G = nx.DiGraph()
    a = _add_node(G, "echo A")
    c = _add_node(G, "echo C")
    G.add_edge(a, c, id=str(uuid.uuid4()))
    edit.save_graph(G, temp_graph_file)

    ctx = mock_server_context
    start_graph_worker(ctx)
    time.sleep(0.05)
    run_id = str(uuid.uuid4())

    ctx.active_node_run[a] = run_id
    ctx.enqueue_status(temp_graph_file, "node", a, "ran", run_id)
    ctx.mod_queue.join()
    time.sleep(0.05)
    assert edit.load_graph(temp_graph_file).nodes[c]["status"] == "run"


def test_blocking_cycle_prevents_run(temp_graph_file):
    """Blocking cycles should be detected before runs start."""
    G = nx.DiGraph()
    n1 = _add_node(G, "echo 1")
    n2 = _add_node(G, "echo 2")
    G.add_edge(n1, n2, id=str(uuid.uuid4()), edge_type="blocking")
    G.add_edge(n2, n1, id=str(uuid.uuid4()), edge_type="blocking")
    edit.save_graph(G, temp_graph_file)

    assert edit.has_blocking_cycle(temp_graph_file) is True


def test_log_overwrite_on_reexecution(temp_graph_file):
    """Subsequent log writes should overwrite prior values."""
    G = nx.DiGraph()
    node_id = _add_node(G, "echo X")
    edit.save_graph(G, temp_graph_file)

    edit.save_node_execution_data_in_graph(temp_graph_file, node_id, "cmd1", "out1", "err1", "1", "0")
    edit.save_node_execution_data_in_graph(temp_graph_file, node_id, "cmd2", "out2", "err2", "2", "1")

    G2 = edit.load_graph(temp_graph_file)
    node = G2.nodes[node_id]
    assert node.get("command") == "cmd2"
    assert node.get("stdout") == "out2"
    assert node.get("stderr") == "err2"
    assert node.get("pid") == "2"
    assert node.get("error_code") == "1"
*** End File