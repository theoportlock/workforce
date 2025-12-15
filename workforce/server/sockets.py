from flask import request
import logging

log = logging.getLogger(__name__)

def register_socket_handlers(socketio, ctx):
    @socketio.on("connect")
    def on_connect(auth=None):
        log.info("SocketIO client connected: %s", request.sid)
        # Do not auto-start runs on connect; runs are explicitly started via POST /run

    @socketio.on("disconnect")
    def on_disconnect():
        log.info("SocketIO client disconnected: %s", request.sid)
