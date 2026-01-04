from flask import request
from flask_socketio import SocketIO, join_room, emit
import logging

log = logging.getLogger(__name__)


def register_socket_handlers(socketio):
    """Register global socket handlers (before_connect, after_connect, disconnect)."""
    
    @socketio.on("connect")
    def on_connect(auth=None):
        """Handle client connection. Workspace ID should be passed in auth or query."""
        log.info(f"SocketIO client connected: {request.sid}")
        # Client must join workspace room on connect
        # This is handled by client library after connect

    @socketio.on("join_room")
    def on_join_room(data):
        """Handle client joining a workspace room."""
        room = data.get("room")
        if room:
            join_room(room)
            log.info(f"Client {request.sid} joined room {room}")
        else:
            log.warning(f"Client {request.sid} tried to join room without room name")

    @socketio.on("disconnect")
    def on_disconnect():
        """Handle client disconnection. Context cleanup is done via REST."""
        log.info(f"SocketIO client disconnected: {request.sid}")


def register_event_handlers(ctx):
    """Register event handlers that translate domain events to workspace room broadcasts.
    
    Each workspace context has its own EventBus subscription that emits to its workspace room.
    """
    from workforce.server.events import Event
    
    workspace_id = ctx.workspace_id
    workspace_room = f"ws:{workspace_id}"
    
    def handle_graph_update(event: Event):
        """Broadcast graph updates to workspace room."""
        try:
            log.info(f"Broadcasting graph_update to room {workspace_room} with {len(event.payload.get('nodes', []))} nodes")
            ctx.socketio.emit("graph_update", event.payload, room=workspace_room)
        except Exception:
            log.exception(f"Failed to emit graph_update to room {workspace_room}")
    
    def handle_node_ready(event: Event):
        """Notify runner clients that a node is ready to execute."""
        try:
            ctx.socketio.emit("node_ready", event.payload, room=workspace_room)
        except Exception:
            log.exception(f"Failed to emit node_ready to room {workspace_room}")
    
    def handle_node_status_change(event: Event):
        """Notify GUI of node status changes (started/finished/failed)."""
        try:
            ctx.socketio.emit("status_change", event.payload, room=workspace_room)
        except Exception:
            log.exception(f"Failed to emit status_change to room {workspace_room}")
    
    def handle_run_complete(event: Event):
        """Notify clients that a run has completed."""
        try:
            ctx.socketio.emit("run_complete", event.payload, room=workspace_room)
        except Exception:
            log.exception(f"Failed to emit run_complete to room {workspace_room}")
    
    # Subscribe handlers to event types
    # Events emitted by this context's worker will trigger these handlers
    ctx.events.subscribe("GRAPH_UPDATED", handle_graph_update)
    ctx.events.subscribe("NODE_READY", handle_node_ready)
    ctx.events.subscribe("NODE_STARTED", handle_node_status_change)
    ctx.events.subscribe("NODE_FINISHED", handle_node_status_change)
    ctx.events.subscribe("NODE_FAILED", handle_node_status_change)
    ctx.events.subscribe("RUN_COMPLETE", handle_run_complete)
    
    log.info(f"Registered SocketIO event handlers for workspace {workspace_id}")
