from flask import request
from flask_socketio import SocketIO, join_room, emit
import logging
from workforce import utils
from .shutdown import shutdown_if_idle

log = logging.getLogger(__name__)

socketio = SocketIO(cors_allowed_origins="*", async_mode="threading")

def register_socket_handlers(socketio, ctx):
    @socketio.on("connect")
    def on_connect(auth=None):
        log.info("SocketIO client connected: %s", request.sid)
        # Do not auto-start runs on connect; runs are explicitly started via POST /run

    @socketio.on("disconnect")
    def on_disconnect():
        log.info("SocketIO client disconnected: %s", request.sid)
        # Don't decrement here - only via REST /client-disconnect endpoint
        # SocketIO disconnect can fire multiple times or independently of GUI exit
        log.debug("SocketIO disconnect does not modify client count (use /client-disconnect)")

    @socketio.on("subscribe")
    def on_subscribe(data):
        path = (data or {}).get("path")
        if not path:
            return emit("error", {"message": "subscribe requires 'path'"})
        join_room(path)
        emit("subscribed", {"path": path})


def register_event_handlers(ctx):
    """Register event handlers that translate domain events to SocketIO messages.
    
    These handlers maintain the existing SocketIO protocol for GUI compatibility.
    """
    from workforce.server.events import Event
    
    def handle_graph_update(event: Event):
        """Broadcast graph updates to all clients."""
        try:
            ctx.socketio.emit("graph_update", event.payload, skip_sid=None)
        except Exception:
            log.exception("Failed to emit graph_update via event handler")
    
    def handle_node_ready(event: Event):
        """Notify runner clients that a node is ready to execute."""
        try:
            ctx.socketio.emit("node_ready", event.payload, skip_sid=None)
        except Exception:
            log.exception("Failed to emit node_ready via event handler")
    
    def handle_node_status_change(event: Event):
        """Notify GUI of node status changes (started/finished/failed)."""
        try:
            ctx.socketio.emit("status_change", event.payload, skip_sid=None)
        except Exception:
            log.exception("Failed to emit status_change via event handler")
    
    def handle_run_complete(event: Event):
        """Notify clients that a run has completed."""
        try:
            ctx.socketio.emit("run_complete", event.payload)
        except Exception:
            log.exception("Failed to emit run_complete via event handler")
    
    # Subscribe handlers to event types
    ctx.events.subscribe("GRAPH_UPDATED", handle_graph_update)
    ctx.events.subscribe("NODE_READY", handle_node_ready)
    ctx.events.subscribe("NODE_STARTED", handle_node_status_change)
    ctx.events.subscribe("NODE_FINISHED", handle_node_status_change)
    ctx.events.subscribe("NODE_FAILED", handle_node_status_change)
    ctx.events.subscribe("RUN_COMPLETE", handle_run_complete)
    
    log.info("Registered SocketIO event handlers")
