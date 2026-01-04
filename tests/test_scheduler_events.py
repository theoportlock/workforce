"""Tests for scheduler event emission."""

import os
import uuid
import queue as std_queue
import tempfile
import threading
import time
from unittest.mock import Mock

import networkx as nx

from workforce import edit
from workforce.server.context import ServerContext
from workforce.server.events import Event
from workforce.server.queue import start_graph_worker


def create_test_context(path):
    """Create a ServerContext for testing."""
    workspace_id = f"ws_test_{uuid.uuid4().hex[:8]}"
    with tempfile.TemporaryDirectory() as cache_dir:
        ctx = ServerContext(
            workspace_id=workspace_id,
            workfile_path=path,
            server_cache_dir=cache_dir,
            mod_queue=std_queue.Queue(),
            socketio=Mock()  # Mock socketio to avoid needing a real server
        )
        return ctx


def test_node_status_change_emits_events():
    """Test that changing node status emits appropriate events."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "test.graphml")
        
        # Create a simple graph
        node = edit.graph.add_node_to_graph(path, "Test Node")
        node_id = node["node_id"]
        
        ctx = create_test_context(path)
        
        # Track emitted events
        emitted_events = []
        
        def track_event(event):
            emitted_events.append(event)
        
        # Subscribe to all event types
        ctx.events.subscribe("NODE_READY", track_event)
        ctx.events.subscribe("NODE_STARTED", track_event)
        ctx.events.subscribe("NODE_FINISHED", track_event)
        ctx.events.subscribe("GRAPH_UPDATED", track_event)
        
        # Start graph worker
        worker_thread = threading.Thread(target=start_graph_worker, args=(ctx,), daemon=True)
        worker_thread.start()
        
        # Change node to "run" status
        ctx.enqueue_status(path, "node", node_id, "run", run_id="test-run")
        
        # Wait for processing
        time.sleep(0.2)
        ctx.mod_queue.join()
        
        # Check that events were emitted
        event_types = [e.type for e in emitted_events]
        assert "GRAPH_UPDATED" in event_types
        assert "NODE_READY" in event_types
        
        # Check NODE_READY payload
        node_ready_events = [e for e in emitted_events if e.type == "NODE_READY"]
        assert len(node_ready_events) == 1
        assert node_ready_events[0].payload["node_id"] == node_id
        assert node_ready_events[0].payload["run_id"] == "test-run"


def test_node_completion_emits_finished_event():
    """Test that marking a node as 'ran' emits NODE_FINISHED."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "test.graphml")
        
        # Create graph with one node
        node = edit.graph.add_node_to_graph(path, "Test Node")
        node_id = node["node_id"]
        
        ctx = create_test_context(path)
        
        emitted_events = []
        
        def track_event(event):
            emitted_events.append(event)
        
        ctx.events.subscribe("NODE_FINISHED", track_event)
        ctx.events.subscribe("GRAPH_UPDATED", track_event)
        
        worker_thread = threading.Thread(target=start_graph_worker, args=(ctx,), daemon=True)
        worker_thread.start()
        
        # Mark node as completed
        ctx.enqueue_status(path, "node", node_id, "ran", run_id="test-run")
        
        time.sleep(0.2)
        ctx.mod_queue.join()
        
        # Check NODE_FINISHED was emitted
        finished_events = [e for e in emitted_events if e.type == "NODE_FINISHED"]
        assert len(finished_events) == 1
        assert finished_events[0].payload["node_id"] == node_id
        assert finished_events[0].payload["status"] == "ran"


def test_node_failure_emits_failed_event():
    """Test that marking a node as 'fail' emits NODE_FAILED."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "test.graphml")
        
        node = edit.graph.add_node_to_graph(path, "Test Node")
        node_id = node["node_id"]
        
        ctx = create_test_context(path)
        
        emitted_events = []
        
        def track_event(event):
            emitted_events.append(event)
        
        ctx.events.subscribe("NODE_FAILED", track_event)
        ctx.events.subscribe("GRAPH_UPDATED", track_event)
        
        worker_thread = threading.Thread(target=start_graph_worker, args=(ctx,), daemon=True)
        worker_thread.start()
        
        ctx.enqueue_status(path, "node", node_id, "fail", run_id="test-run")
        
        time.sleep(0.2)
        ctx.mod_queue.join()
        
        failed_events = [e for e in emitted_events if e.type == "NODE_FAILED"]
        assert len(failed_events) == 1
        assert failed_events[0].payload["node_id"] == node_id
        assert failed_events[0].payload["status"] == "fail"


def test_run_completion_emits_event():
    """Test that completing a run emits RUN_COMPLETE.
    
    Note: Run completion detection uses socketio.start_background_task, which won't
    work with a Mock. This test verifies the mechanism by manually running the check.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "test.graphml")
        
        # Create a simple graph with one node
        node = edit.graph.add_node_to_graph(path, "Test Node")
        node_id = node["node_id"]
        
        ctx = create_test_context(path)
        
        # Make socketio.start_background_task actually execute the task synchronously
        def sync_background_task(func):
            func()
        
        ctx.socketio.start_background_task.side_effect = sync_background_task
        
        emitted_events = []
        
        def track_event(event):
            emitted_events.append(event)
        
        ctx.events.subscribe("RUN_COMPLETE", track_event)
        ctx.events.subscribe("GRAPH_UPDATED", track_event)
        
        worker_thread = threading.Thread(target=start_graph_worker, args=(ctx,), daemon=True)
        worker_thread.start()
        
        run_id = "test-run-complete"
        
        # Start run by marking node as "run"
        ctx.enqueue_status(path, "node", node_id, "run", run_id=run_id)
        time.sleep(0.1)
        
        # Complete it
        ctx.enqueue_status(path, "node", node_id, "ran", run_id=run_id)
        
        # Wait for processing and completion check
        ctx.mod_queue.join()
        time.sleep(0.2)  # Give time for background task
        
        # Check RUN_COMPLETE was emitted
        complete_events = [e for e in emitted_events if e.type == "RUN_COMPLETE"]
        assert len(complete_events) >= 1, f"Expected RUN_COMPLETE event but got: {[e.type for e in emitted_events]}"
        assert complete_events[0].payload["run_id"] == run_id


def test_graph_update_emitted_on_every_change():
    """Test that GRAPH_UPDATED is emitted for all graph modifications."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "test.graphml")
        
        # Create initial graph
        node = edit.graph.add_node_to_graph(path, "Test Node")
        node_id = node["node_id"]
        
        ctx = create_test_context(path)
        
        graph_updates = []
        
        def track_graph_update(event):
            graph_updates.append(event)
        
        ctx.events.subscribe("GRAPH_UPDATED", track_graph_update)
        
        worker_thread = threading.Thread(target=start_graph_worker, args=(ctx,), daemon=True)
        worker_thread.start()
        
        # Make several changes
        ctx.enqueue(edit.graph.edit_node_label_in_graph, path, node_id, "New Label")
        time.sleep(0.1)
        
        ctx.enqueue(edit.graph.edit_node_position_in_graph, path, node_id, 100, 200)
        time.sleep(0.1)
        
        ctx.enqueue_status(path, "node", node_id, "run", run_id="test")
        time.sleep(0.1)
        
        ctx.mod_queue.join()
        
        # Each operation should emit GRAPH_UPDATED
        assert len(graph_updates) >= 3


def test_events_without_socketio():
    """Test that events are emitted even without a real SocketIO server."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "test.graphml")
        
        node = edit.graph.add_node_to_graph(path, "Test Node")
        node_id = node["node_id"]
        
        # Create context without SocketIO
        ctx = ServerContext(
            workspace_id="ws_test_nosos",
            workfile_path=path,
            server_cache_dir=tmpdir,
            mod_queue=std_queue.Queue()
        )
        ctx.socketio = None  # No socketio
        
        emitted_events = []
        
        def track_event(event):
            emitted_events.append(event)
        
        ctx.events.subscribe("NODE_READY", track_event)
        ctx.events.subscribe("GRAPH_UPDATED", track_event)
        
        worker_thread = threading.Thread(target=start_graph_worker, args=(ctx,), daemon=True)
        worker_thread.start()
        
        # This should work without SocketIO
        ctx.enqueue_status(path, "node", node_id, "run", run_id="test")
        
        time.sleep(0.2)
        ctx.mod_queue.join()
        
        # Events should still be emitted
        assert len(emitted_events) > 0
        event_types = [e.type for e in emitted_events]
        assert "NODE_READY" in event_types
