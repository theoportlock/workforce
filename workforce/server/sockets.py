from flask import request
from flask_socketio import SocketIO, join_room, emit
import logging

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

    @socketio.on("subscribe")
    def on_subscribe(data):
        path = (data or {}).get("path")
        if not path:
            return emit("error", {"message": "subscribe requires 'path'"})
        join_room(path)
        emit("subscribed", {"path": path})
