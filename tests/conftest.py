"""Shared test fixtures for all tests."""

import pytest
import uuid
import os
import tempfile
import queue
from unittest.mock import MagicMock
from workforce.server.context import ServerContext
from workforce.server import sockets


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
