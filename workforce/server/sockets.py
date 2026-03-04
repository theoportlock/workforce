from flask import request
from flask_socketio import join_room, emit
import logging
import networkx as nx

log = logging.getLogger(__name__)

# Import edit module for graph loading
from workforce import edit


def _get_graph_data(ctx) -> dict:
    """Load and serialize current graph state for a workspace."""
    G = edit.load_graph(ctx.workfile_path)
    data = nx.node_link_data(G, edges="links")

    heavyweight_attrs = {"log", "stdout", "stderr", "pid", "command", "error_code"}
    for node in data.get("nodes", []):
        for attr in heavyweight_attrs:
            node.pop(attr, None)

    data["graph"] = G.graph
    data["graph"].setdefault("wrapper", "{}")
    return data


def register_socket_handlers(socketio):
    """Register global socket handlers (before_connect, after_connect, disconnect)."""

    @socketio.on("connect")
    def on_connect(auth=None):
        """Handle client connection. Workspace ID should be passed in auth or query."""
        log.info(f"[SocketIO] Client connected: {request.sid}")

    @socketio.on("join_room")
    def on_join_room(data):
        """Handle client joining a workspace room."""
        room = data.get("room")
        if room:
            join_room(room)
            log.info(f"[SocketIO] Client {request.sid} joined room {room}")

            # Extract workspace_id from room name (format: "ws:{workspace_id}")
            if room.startswith("ws:"):
                workspace_id = room[3:]
                from workforce.server import get_context

                ctx = get_context(workspace_id)
                if ctx:
                    try:
                        graph_data = _get_graph_data(ctx)
                        emit("initial_state", graph_data)
                        log.info(
                            f"[SocketIO] Sent initial_state to {request.sid} for workspace {workspace_id}"
                        )
                    except Exception:
                        log.exception(
                            f"[SocketIO] Failed to send initial_state to {request.sid}"
                        )
                else:
                    log.warning(
                        f"[SocketIO] No context found for workspace {workspace_id}"
                    )
        else:
            log.warning(
                f"[SocketIO] Client {request.sid} tried to join room without room name"
            )

    @socketio.on("disconnect")
    def on_disconnect():
        """Handle client disconnection. Context cleanup is done via REST."""
        log.info(f"[SocketIO] Client disconnected: {request.sid}")


def register_event_handlers(ctx):
    """Register event handlers that translate domain events to workspace room broadcasts.

    Each workspace context has its own EventBus subscription that emits to its workspace room.
    """
    from workforce.server.events import Event

    workspace_id = ctx.workspace_id
    workspace_room = f"ws:{workspace_id}"

    log.info(
        f"[SocketIO] Registering event handlers for workspace {workspace_id}, room {workspace_room}"
    )

    def handle_graph_update(event: Event):
        """Broadcast graph updates to workspace room."""
        try:
            node_count = len(event.payload.get("nodes", []))
            link_count = len(event.payload.get("links", []))
            log.info(
                f"[SocketIO] Broadcasting graph_update to room {workspace_room}: {node_count} nodes, {link_count} links, op={event.payload.get('op')}"
            )
            ctx.socketio.emit("graph_update", event.payload, room=workspace_room)
            log.info(
                f"[SocketIO] Successfully emitted graph_update to room {workspace_room}"
            )
        except Exception:
            log.exception(f"Failed to emit graph_update to room {workspace_room}")

    def handle_node_ready(event: Event):
        """Notify runner clients that a node is ready to execute."""
        try:
            log.info(
                f"[SocketIO] Broadcasting node_ready to room {workspace_room}: {event.payload}"
            )
            ctx.socketio.emit("node_ready", event.payload, room=workspace_room)
        except Exception:
            log.exception(f"Failed to emit node_ready to room {workspace_room}")

    def handle_node_status_change(event: Event):
        """Notify GUI of node status changes (started/finished/failed)."""
        try:
            log.info(
                f"[SocketIO] Broadcasting status_change to room {workspace_room}: {event.payload}"
            )
            ctx.socketio.emit("status_change", event.payload, room=workspace_room)
        except Exception:
            log.exception(f"Failed to emit status_change to room {workspace_room}")

    def handle_run_complete(event: Event):
        """Notify clients that a run has completed."""
        try:
            log.info(
                f"[SocketIO] Broadcasting run_complete to room {workspace_room}: {event.payload}"
            )
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
