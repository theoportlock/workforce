#!/usr/bin/env python3
import pytest
import networkx as nx
import subprocess
from unittest.mock import MagicMock
import workforce.runner as runner


# --- Fixtures -----------------------------------------------------------------

@pytest.fixture
def nx_graph():
    """Return a simple directed NetworkX graph with one edge A->B."""
    G = nx.DiGraph()
    G.add_node("A", status="")
    G.add_node("B", status="")
    G.add_edge("A", "B", status="")
    return G


@pytest.fixture
def mock_requests(monkeypatch):
    """Mock requests.get and requests.post for all tests."""
    get_mock = MagicMock()
    post_mock = MagicMock()
    get_mock.return_value.json.return_value = {
        "graph": nx.DiGraph(),
        "nodes": [{"id": "A", "status": "run"}, {"id": "B", "status": ""}],
        "links": [{"source": "A", "target": "B"}],
    }
    post_mock.return_value.status_code = 200
    post_mock.return_value.json.return_value = {"result": "ok"}
    monkeypatch.setattr(runner.requests, "get", get_mock)
    monkeypatch.setattr(runner.requests, "post", post_mock)
    return get_mock, post_mock


@pytest.fixture
def mock_socketio(monkeypatch):
    """Mock socketio.Client so no real connection occurs."""
    mock_client = MagicMock()
    monkeypatch.setattr(runner.socketio, "Client", lambda: mock_client)
    return mock_client


@pytest.fixture
def mock_subprocess(monkeypatch):
    """Mock subprocess so no external processes are spawned."""
    mock_popen = MagicMock()
    mock_run = MagicMock()
    monkeypatch.setattr(runner.subprocess, "Popen", mock_popen)
    monkeypatch.setattr(runner.subprocess, "run", mock_run)
    return mock_popen, mock_run


# --- Tests --------------------------------------------------------------------

def test_edit_status_node_and_edge(nx_graph):
    G = nx_graph
    runner.edit_status(G, "node", "A", "running")
    assert G.nodes["A"]["status"] == "running"

    runner.edit_status(G, "edge", ("A", "B"), "done")
    assert G.edges[("A", "B")]["status"] == "done"

    with pytest.raises(ValueError):
        runner.edit_status(G, "node", "Z", "fail")


def test_save_graph(mock_requests, mock_socketio, nx_graph):
    _, post_mock = mock_requests
    result = runner.save_graph("test.graphml", nx_graph)
    assert result == {"result": "ok"}
    post_mock.assert_called_once()


def test_run_tasks_starts_node(mock_requests, mock_subprocess, nx_graph):
    mock_requests[0].return_value.json.return_value = {
        "graph": {"prefix": "", "suffix": ""},
        "nodes": [{"id": "A", "status": "run"}],
        "links": [],
    }
    mock_popen, _ = mock_subprocess
    runner.run_tasks("test.graphml")
    mock_popen.assert_called_once()
    args = mock_popen.call_args[0][0]
    assert "workforce" in args


def test_initialize_pipeline_resets_failed_nodes(mock_requests, nx_graph):
    mock_requests[0].return_value.json.return_value = {
        "graph": nx_graph,
        "nodes": [{"id": "A", "status": "fail"}],
        "links": [],
    }
    runner.initialize_pipeline("test.graphml")
    mock_requests[1].assert_called_once()


def test_schedule_tasks_sets_to_run(mock_requests, nx_graph):
    mock_requests[0].return_value.json.return_value = {
        "graph": nx_graph,
        "nodes": [{"id": "A", "status": "ran"}, {"id": "B", "status": ""}],
        "links": [{"source": "A", "target": "B"}],
    }
    result = runner.schedule_tasks("test.graphml")
    assert result in (None, "complete")


def test_shell_quote_multiline():
    s = "echo 'hi'\nnext"
    quoted = runner.shell_quote_multiline(s)
    assert "'" in quoted


def test_run_node_success(mock_requests, mock_subprocess):
    _, mock_run = mock_subprocess
    mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0)
    runner.run_node("test.graphml", "A")
    mock_run.assert_called_once()


def test_run_node_failure(mock_requests, mock_subprocess):
    _, mock_run = mock_subprocess
    mock_run.side_effect = subprocess.CalledProcessError(1, "cmd")
    runner.run_node("test.graphml", "A")
    mock_run.assert_called_once()


def test_end_to_end_run(tmp_path, mock_requests, mock_subprocess, nx_graph):
    """Integration-like test using a networkx graph."""
    graph_file = tmp_path / "Workfile.graphml"
    graph_file.write_text("<graphml><graph></graph></graphml>")

    mock_popen, mock_run = mock_subprocess
    mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0)

    runner.initialize_pipeline(str(graph_file))
    runner.schedule_tasks(str(graph_file))
    runner.run_tasks(str(graph_file))
    runner.run_node(str(graph_file), "A")

    assert mock_popen.called or mock_run.called
    _, post_mock = mock_requests
    assert post_mock.called

