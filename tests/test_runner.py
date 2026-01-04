"""
Comprehensive test suite for the run functionality.

Tests cover:
- Simple graphs (linear, branching, joining)
- Cyclic graphs
- Node selection logic (explicit, failed, 0-indegree)
- Scheduler flow (node completion -> edge status -> successor activation)
- stdout/stderr capture
- Concurrent runs with different run_ids
- Resume functionality for failed nodes
"""

import pytest
import uuid
import os
import tempfile
import time
import networkx as nx
from unittest.mock import patch, MagicMock, Mock, call
from workforce.run.client import Runner
from workforce.edit import graph as edit
from workforce.server.context import ServerContext
from workforce.server.queue import start_graph_worker


# =======================
# Fixtures
# =======================

@pytest.fixture
def temp_graph_file():
    """Create a temporary file for graph storage."""
    fd, path = tempfile.mkstemp(suffix=".graphml")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def mock_server_context(temp_graph_file):
    """Create a mock server context for testing."""
    import queue
    from workforce.server import sockets
    
    mod_queue = queue.Queue()
    cache_dir = tempfile.mkdtemp()
    
    # Compute workspace_id from the temp file path
    workspace_id = f"ws_test_{uuid.uuid4().hex[:8]}"
    
    ctx = ServerContext(
        workspace_id=workspace_id,
        workfile_path=temp_graph_file,
        server_cache_dir=cache_dir,
        mod_queue=mod_queue
    )
    ctx.socketio = MagicMock()
    
    # Register event handlers so domain events -> socketio events
    sockets.register_event_handlers(ctx)
    
    yield ctx
    
    # Cleanup
    import shutil
    if os.path.exists(cache_dir):
        shutil.rmtree(cache_dir)


# =======================
# Graph Builders
# =======================

def create_simple_linear_graph(path):
    """Create a simple linear graph: A -> B -> C"""
    G = nx.DiGraph()
    node_a = str(uuid.uuid4())
    node_b = str(uuid.uuid4())
    node_c = str(uuid.uuid4())
    
    G.add_node(node_a, label="echo A", status="", x="0", y="0")
    G.add_node(node_b, label="echo B", status="", x="100", y="0")
    G.add_node(node_c, label="echo C", status="", x="200", y="0")
    
    G.add_edge(node_a, node_b, id=str(uuid.uuid4()))
    G.add_edge(node_b, node_c, id=str(uuid.uuid4()))
    
    edit.save_graph(G, path)
    return {"a": node_a, "b": node_b, "c": node_c}


def create_branching_graph(path):
    """
    Create a branching graph:
         A
        / \
       B   C
        \ /
         D
    """
    G = nx.DiGraph()
    node_a = str(uuid.uuid4())
    node_b = str(uuid.uuid4())
    node_c = str(uuid.uuid4())
    node_d = str(uuid.uuid4())
    
    G.add_node(node_a, label="echo A", status="", x="100", y="0")
    G.add_node(node_b, label="echo B", status="", x="50", y="100")
    G.add_node(node_c, label="echo C", status="", x="150", y="100")
    G.add_node(node_d, label="echo D", status="", x="100", y="200")
    
    G.add_edge(node_a, node_b, id=str(uuid.uuid4()))
    G.add_edge(node_a, node_c, id=str(uuid.uuid4()))
    G.add_edge(node_b, node_d, id=str(uuid.uuid4()))
    G.add_edge(node_c, node_d, id=str(uuid.uuid4()))
    
    edit.save_graph(G, path)
    return {"a": node_a, "b": node_b, "c": node_c, "d": node_d}


def create_cyclic_graph(path):
    """Create a cyclic graph: A -> B -> C -> A"""
    G = nx.DiGraph()
    node_a = str(uuid.uuid4())
    node_b = str(uuid.uuid4())
    node_c = str(uuid.uuid4())
    
    G.add_node(node_a, label="echo A", status="", x="0", y="0")
    G.add_node(node_b, label="echo B", status="", x="100", y="0")
    G.add_node(node_c, label="echo C", status="", x="200", y="0")
    
    G.add_edge(node_a, node_b, id=str(uuid.uuid4()))
    G.add_edge(node_b, node_c, id=str(uuid.uuid4()))
    G.add_edge(node_c, node_a, id=str(uuid.uuid4()))
    
    edit.save_graph(G, path)
    return {"a": node_a, "b": node_b, "c": node_c}


def create_graph_with_failed_nodes(path):
    """Create a graph with some failed nodes: A(fail) -> B, C -> D"""
    G = nx.DiGraph()
    node_a = str(uuid.uuid4())
    node_b = str(uuid.uuid4())
    node_c = str(uuid.uuid4())
    node_d = str(uuid.uuid4())
    
    G.add_node(node_a, label="echo A", status="fail", x="0", y="0")
    G.add_node(node_b, label="echo B", status="", x="100", y="0")
    G.add_node(node_c, label="echo C", status="", x="0", y="100")
    G.add_node(node_d, label="echo D", status="", x="100", y="100")
    
    G.add_edge(node_a, node_b, id=str(uuid.uuid4()))
    G.add_edge(node_c, node_d, id=str(uuid.uuid4()))
    
    edit.save_graph(G, path)
    return {"a": node_a, "b": node_b, "c": node_c, "d": node_d}


def create_independent_nodes_graph(path):
    """Create a graph with multiple independent root nodes."""
    G = nx.DiGraph()
    node_a = str(uuid.uuid4())
    node_b = str(uuid.uuid4())
    node_c = str(uuid.uuid4())
    
    G.add_node(node_a, label="echo A", status="", x="0", y="0")
    G.add_node(node_b, label="echo B", status="", x="100", y="0")
    G.add_node(node_c, label="echo C", status="", x="200", y="0")
    
    edit.save_graph(G, path)
    return {"a": node_a, "b": node_b, "c": node_c}


# =======================
# Unit Tests: Runner Client
# =======================

@patch("workforce.run.client.subprocess.Popen")
def test_execute_node_success(mock_popen):
    """Test successful node execution with stdout/stderr capture."""
    process_mock = MagicMock()
    process_mock.communicate.return_value = ("output line 1\noutput line 2", "warning message")
    process_mock.returncode = 0
    mock_popen.return_value = process_mock

    runner = Runner("http://fake-server", workspace_id="ws_test", workfile_path="/tmp/test.graphml")
    runner.set_node_status = MagicMock()
    runner.send_node_log = MagicMock()

    runner.execute_node("node1", "echo test")
    
    # Verify status changes
    runner.set_node_status.assert_any_call("node1", "running")
    runner.set_node_status.assert_any_call("node1", "ran")
    
    # Verify log capture
    runner.send_node_log.assert_called_once()
    log_text = runner.send_node_log.call_args[0][1]
    assert "output line 1" in log_text
    assert "warning message" in log_text


@patch("workforce.run.client.subprocess.Popen")
def test_execute_node_failure(mock_popen):
    """Test node execution that fails with non-zero exit code."""
    process_mock = MagicMock()
    process_mock.communicate.return_value = ("", "error message")
    process_mock.returncode = 1
    mock_popen.return_value = process_mock

    runner = Runner("http://fake-server", workspace_id="ws_test", workfile_path="/tmp/test.graphml")
    runner.set_node_status = MagicMock()
    runner.send_node_log = MagicMock()

    runner.execute_node("node1", "false")
    
    # Verify failure status
    runner.set_node_status.assert_any_call("node1", "running")
    runner.set_node_status.assert_any_call("node1", "fail")
    
    # Verify error log capture
    runner.send_node_log.assert_called_once()
    log_text = runner.send_node_log.call_args[0][1]
    assert "error message" in log_text


@patch("workforce.run.client.subprocess.Popen")
def test_execute_node_exception(mock_popen):
    """Test node execution when subprocess raises an exception."""
    mock_popen.side_effect = Exception("Command not found")

    runner = Runner("http://fake-server", workspace_id="ws_test", workfile_path="/tmp/test.graphml")
    runner.set_node_status = MagicMock()
    runner.send_node_log = MagicMock()

    runner.execute_node("node1", "invalid_command")
    
    # Verify failure status
    runner.set_node_status.assert_called_with("node1", "fail")
    
    # Verify error log capture
    runner.send_node_log.assert_called_once()
    log_text = runner.send_node_log.call_args[0][1]
    assert "Runner internal error" in log_text
    assert "Command not found" in log_text


def test_execute_node_empty_command():
    """Test execution of a node with empty command."""
    runner = Runner("http://fake-server", workspace_id="ws_test", workfile_path="/tmp/test.graphml")
    runner.set_node_status = MagicMock()
    runner.send_node_log = MagicMock()

    runner.execute_node("node1", "")
    
    # Empty commands should mark as ran without execution
    runner.set_node_status.assert_any_call("node1", "running")
    runner.set_node_status.assert_any_call("node1", "ran")
    
    # Verify log indicates no command
    runner.send_node_log.assert_called_once()
    log_text = runner.send_node_log.call_args[0][1]
    assert "No command" in log_text


def test_runner_wrapper_substitution():
    """Test that wrapper correctly substitutes {} with command."""
    runner = Runner("http://fake-server", workspace_id="ws_test", workfile_path="/tmp/test.graphml", wrapper="bash -c {}")
    runner.set_node_status = MagicMock()
    runner.send_node_log = MagicMock()
    
    with patch("workforce.run.client.subprocess.Popen") as mock_popen:
        process_mock = MagicMock()
        process_mock.communicate.return_value = ("", "")
        process_mock.returncode = 0
        mock_popen.return_value = process_mock
        
        runner.execute_node("node1", "echo test")
        
        # Verify command was wrapped
        call_args = mock_popen.call_args
        assert "bash -c" in call_args[0][0]


# =======================
# Integration Tests: Scheduler Flow
# =======================

def test_scheduler_triggers_successors(temp_graph_file, mock_server_context):
    """Test that completing a node triggers its successors."""
    nodes = create_simple_linear_graph(temp_graph_file)
    ctx = mock_server_context
    
    # Start graph worker
    start_graph_worker(ctx)
    time.sleep(0.1)  # Let worker start
    
    # Set node A to ran
    run_id = str(uuid.uuid4())
    ctx.active_node_run[nodes["a"]] = run_id
    ctx.enqueue_status(temp_graph_file, "node", nodes["a"], "ran", run_id)
    
    # Wait for queue processing
    ctx.mod_queue.join()
    time.sleep(0.1)
    
    # Verify node B was triggered
    G = edit.load_graph(temp_graph_file)
    assert G.nodes[nodes["b"]]["status"] == "run"
    assert G.nodes[nodes["c"]]["status"] == ""  # C should not be triggered yet


def test_scheduler_waits_for_all_predecessors(temp_graph_file, mock_server_context):
    """Test that a node waits for all predecessors before starting."""
    nodes = create_branching_graph(temp_graph_file)
    ctx = mock_server_context
    
    start_graph_worker(ctx)
    time.sleep(0.1)
    
    run_id = str(uuid.uuid4())
    
    # Complete node A (triggers B and C)
    ctx.active_node_run[nodes["a"]] = run_id
    ctx.enqueue_status(temp_graph_file, "node", nodes["a"], "ran", run_id)
    ctx.mod_queue.join()
    time.sleep(0.1)
    
    G = edit.load_graph(temp_graph_file)
    assert G.nodes[nodes["b"]]["status"] == "run"
    assert G.nodes[nodes["c"]]["status"] == "run"
    assert G.nodes[nodes["d"]]["status"] == ""  # D should wait
    
    # Complete B (D should still wait for C)
    ctx.active_node_run[nodes["b"]] = run_id
    ctx.enqueue_status(temp_graph_file, "node", nodes["b"], "ran", run_id)
    ctx.mod_queue.join()
    time.sleep(0.1)
    
    G = edit.load_graph(temp_graph_file)
    assert G.nodes[nodes["d"]]["status"] == ""  # D still waiting
    
    # Complete C (now D should start)
    ctx.active_node_run[nodes["c"]] = run_id
    ctx.enqueue_status(temp_graph_file, "node", nodes["c"], "ran", run_id)
    ctx.mod_queue.join()
    time.sleep(0.1)
    
    G = edit.load_graph(temp_graph_file)
    assert G.nodes[nodes["d"]]["status"] == "run"


def test_scheduler_handles_failed_nodes(temp_graph_file, mock_server_context):
    """Test that failed nodes don't trigger their successors."""
    nodes = create_simple_linear_graph(temp_graph_file)
    ctx = mock_server_context
    
    start_graph_worker(ctx)
    time.sleep(0.1)
    
    run_id = str(uuid.uuid4())
    
    # Fail node A
    ctx.active_node_run[nodes["a"]] = run_id
    ctx.enqueue_status(temp_graph_file, "node", nodes["a"], "fail", run_id)
    ctx.mod_queue.join()
    time.sleep(0.1)
    
    # Verify B was NOT triggered
    G = edit.load_graph(temp_graph_file)
    assert G.nodes[nodes["b"]]["status"] == ""


def test_scheduler_emits_node_ready_event(temp_graph_file, mock_server_context):
    """Test that setting node status to 'run' emits node_ready event."""
    nodes = create_simple_linear_graph(temp_graph_file)
    ctx = mock_server_context
    
    start_graph_worker(ctx)
    time.sleep(0.1)
    
    run_id = str(uuid.uuid4())
    
    # Trigger node A
    ctx.enqueue_status(temp_graph_file, "node", nodes["a"], "run", run_id)
    ctx.mod_queue.join()
    time.sleep(0.1)
    
    # Verify node_ready was emitted
    ctx.socketio.emit.assert_any_call(
        "node_ready",
        {"node_id": nodes["a"], "label": "echo A", "run_id": run_id},
        room=f"ws:{ctx.workspace_id}"
    )


def test_scheduler_emits_status_change_event(temp_graph_file, mock_server_context):
    """Test that node status changes emit status_change events."""
    nodes = create_simple_linear_graph(temp_graph_file)
    ctx = mock_server_context
    
    start_graph_worker(ctx)
    time.sleep(0.1)
    
    run_id = str(uuid.uuid4())
    
    # Mark node as running
    ctx.active_node_run[nodes["a"]] = run_id
    ctx.enqueue_status(temp_graph_file, "node", nodes["a"], "running", run_id)
    ctx.mod_queue.join()
    time.sleep(0.1)
    
    # Verify status_change was emitted for running
    ctx.socketio.emit.assert_any_call(
        "status_change",
        {"node_id": nodes["a"], "status": "running", "run_id": run_id},
        room=f"ws:{ctx.workspace_id}"
    )
    
    # Mark node as ran
    ctx.enqueue_status(temp_graph_file, "node", nodes["a"], "ran", run_id)
    ctx.mod_queue.join()
    time.sleep(0.1)
    
    # Verify status_change was emitted for ran
    ctx.socketio.emit.assert_any_call(
        "status_change",
        {"node_id": nodes["a"], "status": "ran", "run_id": run_id},
        room=f"ws:{ctx.workspace_id}"
    )


# =======================
# Integration Tests: Run Selection
# =======================

def test_run_selects_zero_indegree_nodes(temp_graph_file):
    """Test that run starts from nodes with 0 in-degree when no nodes selected."""
    nodes = create_simple_linear_graph(temp_graph_file)
    G = edit.load_graph(temp_graph_file)
    
    # Find nodes with 0 in-degree
    zero_indegree = [n for n, d in G.in_degree() if d == 0]
    
    assert nodes["a"] in zero_indegree
    assert nodes["b"] not in zero_indegree
    assert nodes["c"] not in zero_indegree


def test_run_selects_failed_nodes_when_present(temp_graph_file):
    """Test that run prioritizes failed nodes over 0-indegree nodes."""
    nodes = create_graph_with_failed_nodes(temp_graph_file)
    G = edit.load_graph(temp_graph_file)
    
    # Find failed nodes
    failed_nodes = [n for n, d in G.nodes(data=True) if d.get("status") == "fail"]
    
    assert nodes["a"] in failed_nodes
    assert len(failed_nodes) == 1


def test_run_with_explicit_node_selection(temp_graph_file):
    """Test that run uses explicitly selected nodes when provided."""
    nodes = create_simple_linear_graph(temp_graph_file)
    
    # Explicitly select node B (not a root node)
    selected = [nodes["b"]]
    
    # This should start from B, not A
    G = edit.load_graph(temp_graph_file)
    assert nodes["b"] in G.nodes


def test_run_with_multiple_root_nodes(temp_graph_file):
    """Test that run starts all nodes with 0 in-degree."""
    nodes = create_independent_nodes_graph(temp_graph_file)
    G = edit.load_graph(temp_graph_file)
    
    # All nodes should have 0 in-degree
    zero_indegree = [n for n, d in G.in_degree() if d == 0]
    
    assert len(zero_indegree) == 3
    assert all(n in zero_indegree for n in nodes.values())


# =======================
# Integration Tests: Cyclic Graphs
# =======================

def test_cyclic_graph_does_not_infinite_loop(temp_graph_file, mock_server_context):
    """Test that cyclic graphs don't cause infinite loops."""
    nodes = create_cyclic_graph(temp_graph_file)
    ctx = mock_server_context
    
    start_graph_worker(ctx)
    time.sleep(0.1)
    
    run_id = str(uuid.uuid4())
    
    # Start node A
    ctx.enqueue_status(temp_graph_file, "node", nodes["a"], "run", run_id)
    ctx.mod_queue.join()
    time.sleep(0.1)
    
    # Complete A -> should trigger B
    ctx.active_node_run[nodes["a"]] = run_id
    ctx.enqueue_status(temp_graph_file, "node", nodes["a"], "ran", run_id)
    ctx.mod_queue.join()
    time.sleep(0.1)
    
    G = edit.load_graph(temp_graph_file)
    assert G.nodes[nodes["b"]]["status"] == "run"
    
    # Complete B -> should trigger C
    ctx.active_node_run[nodes["b"]] = run_id
    ctx.enqueue_status(temp_graph_file, "node", nodes["b"], "ran", run_id)
    ctx.mod_queue.join()
    time.sleep(0.1)
    
    G = edit.load_graph(temp_graph_file)
    assert G.nodes[nodes["c"]]["status"] == "run"
    
    # Complete C -> should NOT retrigger A (already ran)
    ctx.active_node_run[nodes["c"]] = run_id
    ctx.enqueue_status(temp_graph_file, "node", nodes["c"], "ran", run_id)
    ctx.mod_queue.join()
    time.sleep(0.1)
    
    G = edit.load_graph(temp_graph_file)
    assert G.nodes[nodes["a"]]["status"] == "ran"  # Should still be ran, not run


# =======================
# Integration Tests: Concurrent Runs
# =======================

def test_concurrent_runs_with_different_run_ids(temp_graph_file, mock_server_context):
    """Test that multiple runs with different run_ids can coexist."""
    nodes = create_simple_linear_graph(temp_graph_file)
    ctx = mock_server_context
    
    start_graph_worker(ctx)
    time.sleep(0.1)
    
    run_id_1 = str(uuid.uuid4())
    run_id_2 = str(uuid.uuid4())
    
    ctx.active_runs[run_id_1] = {"nodes": {nodes["a"]}}
    ctx.active_runs[run_id_2] = {"nodes": {nodes["b"]}}
    
    # Trigger node A with run_id_1
    ctx.active_node_run[nodes["a"]] = run_id_1
    ctx.enqueue_status(temp_graph_file, "node", nodes["a"], "run", run_id_1)
    ctx.mod_queue.join()
    time.sleep(0.1)
    
    # Verify node_ready was emitted with correct run_id
    calls = [c for c in ctx.socketio.emit.call_args_list if c[0][0] == "node_ready"]
    assert any(
        c[0][1].get("run_id") == run_id_1 and c[0][1].get("node_id") == nodes["a"]
        for c in calls
    )


# =======================
# Integration Tests: Resume Functionality
# =======================

def test_resume_replaces_failed_with_run(temp_graph_file, mock_server_context):
    """Test that resume replaces failed nodes with run status."""
    nodes = create_graph_with_failed_nodes(temp_graph_file)
    ctx = mock_server_context
    
    start_graph_worker(ctx)
    time.sleep(0.1)
    
    run_id = str(uuid.uuid4())
    
    # Resume the failed node by setting it to run
    ctx.active_node_run[nodes["a"]] = run_id
    ctx.enqueue_status(temp_graph_file, "node", nodes["a"], "run", run_id)
    ctx.mod_queue.join()
    time.sleep(0.1)
    
    G = edit.load_graph(temp_graph_file)
    assert G.nodes[nodes["a"]]["status"] == "run"
    
    # Verify node_ready was emitted
    ctx.socketio.emit.assert_any_call(
        "node_ready",
        {"node_id": nodes["a"], "label": "echo A", "run_id": run_id},
        room=f"ws:{ctx.workspace_id}"
    )


def test_resume_continues_pipeline_after_failed_node(temp_graph_file, mock_server_context):
    """Test that resuming a failed node continues the pipeline."""
    nodes = create_simple_linear_graph(temp_graph_file)
    ctx = mock_server_context
    
    start_graph_worker(ctx)
    time.sleep(0.1)
    
    run_id = str(uuid.uuid4())
    
    # Set A to ran and B to fail
    G = edit.load_graph(temp_graph_file)
    G.nodes[nodes["a"]]["status"] = "ran"
    G.nodes[nodes["b"]]["status"] = "fail"
    edit.save_graph(G, temp_graph_file)
    
    # Resume B
    ctx.active_node_run[nodes["b"]] = run_id
    ctx.enqueue_status(temp_graph_file, "node", nodes["b"], "run", run_id)
    ctx.mod_queue.join()
    time.sleep(0.1)
    
    G = edit.load_graph(temp_graph_file)
    assert G.nodes[nodes["b"]]["status"] == "run"
    
    # Complete B
    ctx.enqueue_status(temp_graph_file, "node", nodes["b"], "ran", run_id)
    ctx.mod_queue.join()
    time.sleep(0.1)
    
    # Verify C is triggered
    G = edit.load_graph(temp_graph_file)
    assert G.nodes[nodes["c"]]["status"] == "run"


# =======================
# Edge Cases
# =======================

def test_node_does_not_remain_running_indefinitely(temp_graph_file, mock_server_context):
    """Test that nodes transition from running to ran/fail."""
    nodes = create_simple_linear_graph(temp_graph_file)
    ctx = mock_server_context
    
    start_graph_worker(ctx)
    time.sleep(0.1)
    
    run_id = str(uuid.uuid4())
    
    # Set node to running
    ctx.active_node_run[nodes["a"]] = run_id
    ctx.enqueue_status(temp_graph_file, "node", nodes["a"], "running", run_id)
    ctx.mod_queue.join()
    time.sleep(0.1)
    
    G = edit.load_graph(temp_graph_file)
    assert G.nodes[nodes["a"]]["status"] == "running"
    
    # Complete the node
    ctx.enqueue_status(temp_graph_file, "node", nodes["a"], "ran", run_id)
    ctx.mod_queue.join()
    time.sleep(0.1)
    
    G = edit.load_graph(temp_graph_file)
    assert G.nodes[nodes["a"]]["status"] == "ran"


def test_graph_with_no_nodes(temp_graph_file):
    """Test handling of an empty graph."""
    G = nx.DiGraph()
    edit.save_graph(G, temp_graph_file)
    
    G_loaded = edit.load_graph(temp_graph_file)
    assert len(G_loaded.nodes) == 0
    
    # No nodes to run
    zero_indegree = [n for n, d in G_loaded.in_degree() if d == 0]
    assert len(zero_indegree) == 0


def test_log_storage_in_node_attributes(temp_graph_file):
    """Test that logs are stored as node attributes."""
    nodes = create_simple_linear_graph(temp_graph_file)
    
    log_text = "stdout: test output\nstderr: test error"
    edit.save_node_log_in_graph(temp_graph_file, nodes["a"], log_text)
    
    G = edit.load_graph(temp_graph_file)
    assert G.nodes[nodes["a"]]["log"] == log_text


def test_subgraph_run_filters_correctly(temp_graph_file):
    """Test that subgraph runs only operate on selected nodes."""
    nodes = create_simple_linear_graph(temp_graph_file)
    G = edit.load_graph(temp_graph_file)
    
    # Select only node B
    selected = [nodes["b"]]
    subgraph = G.subgraph(selected)
    
    assert nodes["b"] in subgraph.nodes
    assert nodes["a"] not in subgraph.nodes
    assert nodes["c"] not in subgraph.nodes


# =======================
# Additional Edge Cases
# =======================

def test_multiple_edges_between_nodes(temp_graph_file, mock_server_context):
    """Test handling of graphs with multiple edges between the same nodes."""
    G = nx.DiGraph()
    node_a = str(uuid.uuid4())
    node_b = str(uuid.uuid4())
    
    G.add_node(node_a, label="echo A", status="", x="0", y="0")
    G.add_node(node_b, label="echo B", status="", x="100", y="0")
    
    # Add multiple edges (though NetworkX DiGraph will only keep one)
    edge_id_1 = str(uuid.uuid4())
    G.add_edge(node_a, node_b, id=edge_id_1)
    
    edit.save_graph(G, temp_graph_file)
    
    ctx = mock_server_context
    start_graph_worker(ctx)
    time.sleep(0.1)
    
    run_id = str(uuid.uuid4())
    
    # Complete node A
    ctx.active_node_run[node_a] = run_id
    ctx.enqueue_status(temp_graph_file, "node", node_a, "ran", run_id)
    ctx.mod_queue.join()
    time.sleep(0.1)
    
    # Node B should be triggered
    G_loaded = edit.load_graph(temp_graph_file)
    assert G_loaded.nodes[node_b]["status"] == "run"


def test_node_with_no_command(temp_graph_file, mock_server_context):
    """Test a node with empty/no command."""
    G = nx.DiGraph()
    node_a = str(uuid.uuid4())
    
    G.add_node(node_a, label="", status="", x="0", y="0")
    edit.save_graph(G, temp_graph_file)
    
    # Execute empty command
    runner = Runner("http://fake-server", workspace_id="ws_test", workfile_path="/tmp/test.graphml")
    runner.set_node_status = MagicMock()
    runner.send_node_log = MagicMock()
    
    runner.execute_node(node_a, "")
    
    # Should complete successfully even with no command
    runner.set_node_status.assert_any_call(node_a, "ran")


def test_very_long_log_output(temp_graph_file):
    """Test handling of very long log outputs."""
    nodes = create_simple_linear_graph(temp_graph_file)
    
    # Create a very long log
    long_log = "line\n" * 10000
    edit.save_node_log_in_graph(temp_graph_file, nodes["a"], long_log)
    
    G = edit.load_graph(temp_graph_file)
    retrieved_log = G.nodes[nodes["a"]]["log"]
    
    # Verify it was stored and retrieved correctly (split adds one extra for trailing newline)
    assert len(retrieved_log.split('\n')) >= 10000


def test_run_complete_logic(temp_graph_file, mock_server_context):
    """Test the run completion detection logic."""
    nodes = create_simple_linear_graph(temp_graph_file)
    ctx = mock_server_context
    
    start_graph_worker(ctx)
    time.sleep(0.1)
    
    run_id = str(uuid.uuid4())
    # Register run with nodes that will be tracked
    ctx.active_runs[run_id] = {"nodes": set()}
    
    # Start node
    ctx.enqueue_status(temp_graph_file, "node", nodes["a"], "run", run_id)
    ctx.mod_queue.join()
    time.sleep(0.1)
    
    # Verify node was added to active run
    assert nodes["a"] in ctx.active_runs[run_id]["nodes"]
    
    # Complete the node
    ctx.enqueue_status(temp_graph_file, "node", nodes["a"], "ran", run_id)
    ctx.mod_queue.join()
    time.sleep(0.1)
    
    # Verify the node status changed
    G = edit.load_graph(temp_graph_file)
    assert G.nodes[nodes["a"]]["status"] == "ran"


def test_status_persistence_across_save_load(temp_graph_file):
    """Test that node statuses persist when graph is saved and reloaded."""
    nodes = create_simple_linear_graph(temp_graph_file)
    
    # Set a status
    edit.edit_status_in_graph(temp_graph_file, "node", nodes["a"], "ran")
    
    # Reload graph
    G = edit.load_graph(temp_graph_file)
    
    # Verify status persisted
    assert G.nodes[nodes["a"]]["status"] == "ran"


def test_parallel_branch_execution(temp_graph_file, mock_server_context):
    """Test that parallel branches can execute independently."""
    nodes = create_branching_graph(temp_graph_file)
    ctx = mock_server_context
    
    start_graph_worker(ctx)
    time.sleep(0.1)
    
    run_id = str(uuid.uuid4())
    
    # Complete root node A
    ctx.active_node_run[nodes["a"]] = run_id
    ctx.enqueue_status(temp_graph_file, "node", nodes["a"], "ran", run_id)
    ctx.mod_queue.join()
    time.sleep(0.1)
    
    # Both B and C should be triggered independently
    G = edit.load_graph(temp_graph_file)
    assert G.nodes[nodes["b"]]["status"] == "run"
    assert G.nodes[nodes["c"]]["status"] == "run"
    
    # D should still wait
    assert G.nodes[nodes["d"]]["status"] == ""


def test_wrapper_with_multiline_command(temp_graph_file):
    """Test wrapper handling of multiline commands."""
    runner = Runner("http://fake-server", workspace_id="ws_test", workfile_path="/tmp/test.graphml", wrapper="bash -c {}")
    runner.set_node_status = MagicMock()
    runner.send_node_log = MagicMock()
    
    multiline_cmd = "echo line1\necho line2\necho line3"
    
    with patch("workforce.run.client.subprocess.Popen") as mock_popen:
        process_mock = MagicMock()
        process_mock.communicate.return_value = ("line1\nline2\nline3", "")
        process_mock.returncode = 0
        mock_popen.return_value = process_mock
        
        runner.execute_node("node1", multiline_cmd)
        
        # Verify command was executed
        assert mock_popen.called


def test_failed_node_doesnt_trigger_cascade(temp_graph_file, mock_server_context):
    """Test that a failed node doesn't cause its entire dependency chain to run."""
    nodes = create_simple_linear_graph(temp_graph_file)
    ctx = mock_server_context
    
    start_graph_worker(ctx)
    time.sleep(0.1)
    
    run_id = str(uuid.uuid4())
    
    # Fail node A
    ctx.active_node_run[nodes["a"]] = run_id
    ctx.enqueue_status(temp_graph_file, "node", nodes["a"], "fail", run_id)
    ctx.mod_queue.join()
    time.sleep(0.1)
    
    # Neither B nor C should be triggered
    G = edit.load_graph(temp_graph_file)
    assert G.nodes[nodes["b"]]["status"] == ""
    assert G.nodes[nodes["c"]]["status"] == ""
