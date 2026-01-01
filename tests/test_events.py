"""Tests for the event system."""

import os
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock

from workforce.server.events import Event, EventBus


def test_event_creation():
    """Test creating an Event object."""
    event = Event(type="NODE_READY", payload={"node_id": "test_node", "run_id": "abc-123"})
    assert event.type == "NODE_READY"
    assert event.payload["node_id"] == "test_node"
    assert event.payload["run_id"] == "abc-123"


def test_eventbus_subscribe_and_emit():
    """Test subscribing to and emitting events."""
    bus = EventBus()
    handler = Mock()
    
    bus.subscribe("NODE_READY", handler)
    
    event = Event(type="NODE_READY", payload={"node_id": "test"})
    bus.emit(event)
    
    handler.assert_called_once_with(event)


def test_eventbus_multiple_subscribers():
    """Test multiple handlers for the same event type."""
    bus = EventBus()
    handler1 = Mock()
    handler2 = Mock()
    
    bus.subscribe("NODE_READY", handler1)
    bus.subscribe("NODE_READY", handler2)
    
    event = Event(type="NODE_READY", payload={"node_id": "test"})
    bus.emit(event)
    
    handler1.assert_called_once_with(event)
    handler2.assert_called_once_with(event)


def test_eventbus_different_event_types():
    """Test that handlers only receive events they subscribed to."""
    bus = EventBus()
    handler_ready = Mock()
    handler_complete = Mock()
    
    bus.subscribe("NODE_READY", handler_ready)
    bus.subscribe("RUN_COMPLETE", handler_complete)
    
    event1 = Event(type="NODE_READY", payload={"node_id": "test"})
    event2 = Event(type="RUN_COMPLETE", payload={"run_id": "abc-123"})
    
    bus.emit(event1)
    bus.emit(event2)
    
    handler_ready.assert_called_once_with(event1)
    handler_complete.assert_called_once_with(event2)


def test_eventbus_handler_exception_continues():
    """Test that if one handler fails, others still run."""
    bus = EventBus()
    
    def failing_handler(event):
        raise ValueError("Handler failed")
    
    successful_handler = Mock()
    
    bus.subscribe("NODE_READY", failing_handler)
    bus.subscribe("NODE_READY", successful_handler)
    
    event = Event(type="NODE_READY", payload={"node_id": "test"})
    bus.emit(event)
    
    # Second handler should still be called
    successful_handler.assert_called_once_with(event)


def test_eventbus_file_logging():
    """Test that events are logged to file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = os.path.join(tmpdir, "events.log")
        bus = EventBus(log_file=log_file)
        
        event = Event(type="NODE_READY", payload={"node_id": "test_node", "run_id": "abc-123"})
        bus.emit(event)
        
        # Check file was created and contains event
        assert os.path.exists(log_file)
        
        with open(log_file) as f:
            lines = f.readlines()
        
        assert len(lines) == 1
        logged = json.loads(lines[0])
        assert logged["type"] == "NODE_READY"
        assert logged["payload"]["node_id"] == "test_node"
        assert "timestamp" in logged


def test_eventbus_log_rotation():
    """Test that log file rotates when it exceeds max size."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = os.path.join(tmpdir, "events.log")
        # Set very small max size for testing
        bus = EventBus(log_file=log_file, max_log_size=100)
        
        # Emit enough events to trigger rotation
        for i in range(10):
            event = Event(
                type="NODE_READY",
                payload={"node_id": f"node_{i}", "run_id": "abc-123", "extra_data": "x" * 50}
            )
            bus.emit(event)
        
        # Check that rotation occurred
        assert os.path.exists(log_file)
        assert os.path.exists(f"{log_file}.1") or os.path.exists(f"{log_file}.2")


def test_eventbus_no_logging_if_path_none():
    """Test that no logging occurs when log_file is None."""
    bus = EventBus(log_file=None)
    handler = Mock()
    bus.subscribe("NODE_READY", handler)
    
    event = Event(type="NODE_READY", payload={"node_id": "test"})
    bus.emit(event)
    
    # Handler should be called, but no file operations should occur
    handler.assert_called_once_with(event)


def test_all_event_types():
    """Test that all defined event types work."""
    bus = EventBus()
    handler = Mock()
    
    event_types = [
        "NODE_READY",
        "NODE_STARTED",
        "NODE_FINISHED",
        "NODE_FAILED",
        "RUN_COMPLETE",
        "GRAPH_UPDATED",
    ]
    
    for event_type in event_types:
        bus.subscribe(event_type, handler)
        event = Event(type=event_type, payload={"test": "data"})
        bus.emit(event)
    
    assert handler.call_count == len(event_types)
