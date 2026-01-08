"""
Test suite for Save As functionality.

Tests cover:
- Save As endpoint validation
- Active run blocking
- Workspace switching
- File path handling
- Error scenarios
"""

import pytest
import os
import tempfile
import time
import networkx as nx
from unittest.mock import Mock, patch
from workforce.edit import graph as edit
from workforce.server.context import ServerContext
from workforce.server.queue import start_graph_worker
from workforce.server import routes
from workforce import utils
from flask import Flask, g, request
import queue as std_queue


@pytest.fixture
def temp_workfiles():
    """Create temporary workfiles for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        original_file = os.path.join(tmpdir, "original.wf")
        new_file = os.path.join(tmpdir, "new_file.wf")
        
        # Create a simple graph in the original file
        G = nx.DiGraph()
        G.add_node("node1", label="echo 'test'", x=100, y=100, status="ran")
        G.add_node("node2", label="echo 'test2'", x=200, y=200, status="")
        G.add_edge("node1", "node2")
        G.graph["wrapper"] = "{}"
        edit.save_graph(G, original_file)
        
        yield original_file, new_file


@pytest.fixture
def test_app():
    """Create a test Flask app with routes registered."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    routes.register_routes(app)

    @app.before_request
    def _inject_test_ctx():
        # Allow tests to inject contexts per workspace ID without touching server internals
        ctx_map = getattr(app, "test_ctx_map", {})
        if request.path.startswith("/workspace/"):
            parts = request.path.strip("/").split("/")
            if len(parts) >= 2:
                ws_id = parts[1]
                g.ctx = ctx_map.get(ws_id)
                g.workspace_id = ws_id
    
    return app


@pytest.fixture
def mock_context(temp_workfiles):
    """Create a mock ServerContext for testing."""
    original_file, _ = temp_workfiles
    workspace_id = utils.compute_workspace_id(original_file)
    
    ctx = ServerContext(
        workspace_id=workspace_id,
        workfile_path=original_file,
        server_cache_dir=tempfile.mkdtemp(),
        mod_queue=std_queue.Queue(),
        socketio=Mock(),
    )
    
    # Start worker thread
    start_graph_worker(ctx)
    
    yield ctx
    
    # Cleanup
    ctx.mod_queue.put(None)  # Signal worker to stop
    if ctx.worker_thread and ctx.worker_thread.is_alive():
        ctx.worker_thread.join(timeout=2)


def test_save_as_basic(test_app, mock_context, temp_workfiles):
    """Test basic save-as functionality."""
    original_file, new_file = temp_workfiles
    test_app.test_ctx_map = {mock_context.workspace_id: mock_context}
    
    with test_app.test_client() as client:
        response = client.post(
            f"/workspace/{mock_context.workspace_id}/save-as",
            json={"new_path": new_file},
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "saved"
        assert data["new_path"] == new_file
        assert "new_workspace_id" in data
        assert "new_base_url" in data
        
        # Verify new file exists
        assert os.path.exists(new_file)
        
        # Verify graph content was preserved
        G_original = edit.load_graph(original_file)
        G_new = edit.load_graph(new_file)
        
        assert G_original.nodes["node1"]["label"] == G_new.nodes["node1"]["label"]
        assert G_original.nodes["node1"]["status"] == G_new.nodes["node1"]["status"]
        assert G_original.nodes["node2"]["label"] == G_new.nodes["node2"]["label"]
        assert G_original.graph["wrapper"] == G_new.graph["wrapper"]


def test_save_as_preserves_statuses(test_app, mock_context, temp_workfiles):
    """Test that save-as preserves node execution statuses."""
    original_file, new_file = temp_workfiles
    test_app.test_ctx_map = {mock_context.workspace_id: mock_context}
    
    # Add more nodes with various statuses
    G = edit.load_graph(original_file)
    G.add_node("node3", label="echo 'test3'", x=300, y=300, status="fail")
    G.add_node("node4", label="echo 'test4'", x=400, y=400, status="running")
    edit.save_graph(G, original_file)
    
    with test_app.test_client() as client:
        response = client.post(
            f"/workspace/{mock_context.workspace_id}/save-as",
            json={"new_path": new_file}
        )
        
        assert response.status_code == 200
        
        # Verify all statuses preserved
        G_new = edit.load_graph(new_file)
        assert G_new.nodes["node1"]["status"] == "ran"
        assert G_new.nodes["node2"]["status"] == ""
        assert G_new.nodes["node3"]["status"] == "fail"
        assert G_new.nodes["node4"]["status"] == "running"


def test_save_as_blocked_during_active_run(test_app, mock_context, temp_workfiles):
    """Test that save-as is blocked when there are active runs."""
    original_file, new_file = temp_workfiles
    test_app.test_ctx_map = {mock_context.workspace_id: mock_context}
    
    # Simulate an active run
    run_id = "test_run_123"
    mock_context.active_runs[run_id] = {"nodes": {"node1", "node2"}, "subset_only": False}
    
    with test_app.test_client() as client:
        response = client.post(
            f"/workspace/{mock_context.workspace_id}/save-as",
            json={"new_path": new_file}
        )
        
        assert response.status_code == 409  # Conflict
        data = response.get_json()
        assert "error" in data
        assert "Cannot save during active workflow execution" in data["error"]
        
        # Verify new file was NOT created
        assert not os.path.exists(new_file)


def test_save_as_missing_new_path(test_app, mock_context, temp_workfiles):
    """Test that save-as requires new_path parameter."""
    original_file, new_file = temp_workfiles
    test_app.test_ctx_map = {mock_context.workspace_id: mock_context}
    
    with test_app.test_client() as client:
        # Request without new_path
        response = client.post(
            f"/workspace/{mock_context.workspace_id}/save-as",
            json={}
        )
        
        assert response.status_code == 400  # Bad Request
        data = response.get_json()
        assert "error" in data
        assert "new_path required" in data["error"]


def test_save_as_workspace_not_found(test_app):
    """Test save-as with non-existent workspace."""
    test_app.test_ctx_map = {}
    with test_app.test_client() as client:
        response = client.post(
            "/workspace/ws_nonexistent/save-as",
            json={"new_path": "/tmp/test.wf"}
        )
        
        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data
        assert "Workspace not found" in data["error"]


def test_save_as_new_workspace_id_computed(test_app, mock_context, temp_workfiles):
    """Test that save-as computes correct new workspace ID."""
    original_file, new_file = temp_workfiles
    test_app.test_ctx_map = {mock_context.workspace_id: mock_context}
    
    with test_app.test_client() as client:
        response = client.post(
            f"/workspace/{mock_context.workspace_id}/save-as",
            json={"new_path": new_file}
        )
        
        assert response.status_code == 200
        data = response.get_json()
        
        # Verify workspace ID is correctly computed from new path
        expected_workspace_id = utils.compute_workspace_id(new_file)
        assert data["new_workspace_id"] == expected_workspace_id
        
        # Verify URL is correct
        expected_url = utils.get_workspace_url(expected_workspace_id)
        assert data["new_base_url"] == expected_url


def test_save_as_absolute_path_handling(test_app, mock_context, temp_workfiles):
    """Test that save-as handles relative paths by converting to absolute."""
    original_file, new_file = temp_workfiles
    test_app.test_ctx_map = {mock_context.workspace_id: mock_context}
    
    # Use a relative path for testing
    relative_path = "test_relative_save.wf"
    expected_absolute = os.path.abspath(relative_path)
    
    try:
        with test_app.test_client() as client:
            response = client.post(
                f"/workspace/{mock_context.workspace_id}/save-as",
                json={"new_path": relative_path}
            )
            
            assert response.status_code == 200
            data = response.get_json()
            
            # Verify the returned path is absolute
            assert os.path.isabs(data["new_path"])
            assert data["new_path"] == expected_absolute
    finally:
        # Clean up any file created in current working directory
        if os.path.exists(expected_absolute):
            os.remove(expected_absolute)


def test_save_as_integration_with_gui_client():
    """Test that ServerClient.save_as() works correctly."""
    from workforce.gui.client import ServerClient
    
    # Create a mock client
    client = ServerClient(
        base_url="http://127.0.0.1:5042/workspace/ws_test",
        workspace_id="ws_test",
        workfile_path="/tmp/test.wf",
        on_graph_update=None
    )
    
    # Mock the _post function to verify it's called correctly
    with patch('workforce.utils._post') as mock_post:
        mock_post.return_value = {
            "status": "saved",
            "new_path": "/tmp/new.wf",
            "new_workspace_id": "ws_new",
            "new_base_url": "http://127.0.0.1:5042/workspace/ws_new"
        }
        
        result = client.save_as("/tmp/new.wf")
        
        # Verify _post was called with correct parameters
        mock_post.assert_called_once_with(
            "http://127.0.0.1:5042/workspace/ws_test",
            "/save-as",
            {"new_path": "/tmp/new.wf"}
        )
        
        assert result["status"] == "saved"
        assert result["new_workspace_id"] == "ws_new"


def test_save_as_concurrent_workspaces(test_app, temp_workfiles):
    """Test save-as doesn't affect other workspaces."""
    original_file1, new_file1 = temp_workfiles
    
    # Create second workspace
    with tempfile.TemporaryDirectory() as tmpdir2:
        original_file2 = os.path.join(tmpdir2, "other.wf")
        G2 = nx.DiGraph()
        G2.add_node("other_node", label="echo 'other'", x=100, y=100)
        edit.save_graph(G2, original_file2)
        
        workspace_id1 = utils.compute_workspace_id(original_file1)
        workspace_id2 = utils.compute_workspace_id(original_file2)
        
        ctx1 = ServerContext(
            workspace_id=workspace_id1,
            workfile_path=original_file1,
            server_cache_dir=tempfile.mkdtemp(),
            mod_queue=std_queue.Queue(),
            socketio=Mock(),
        )
        
        ctx2 = ServerContext(
            workspace_id=workspace_id2,
            workfile_path=original_file2,
            server_cache_dir=tempfile.mkdtemp(),
            mod_queue=std_queue.Queue(),
            socketio=Mock(),
        )
        
        start_graph_worker(ctx1)
        start_graph_worker(ctx2)

        try:
            test_app.test_ctx_map = {workspace_id1: ctx1, workspace_id2: ctx2}
            with test_app.test_client() as client:
                response = client.post(
                    f"/workspace/{workspace_id1}/save-as",
                    json={"new_path": new_file1}
                )
                assert response.status_code == 200

            # Verify workspace 2 is unaffected
            assert ctx2.workfile_path == original_file2
            G2_check = edit.load_graph(original_file2)
            assert "other_node" in G2_check.nodes

        finally:
            # Cleanup
            ctx1.mod_queue.put(None)
            ctx2.mod_queue.put(None)
            for ctx in [ctx1, ctx2]:
                if ctx.worker_thread and ctx.worker_thread.is_alive():
                    ctx.worker_thread.join(timeout=2)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
