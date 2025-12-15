import os
import platform
import signal
import subprocess
import queue
import uuid
import sys
import logging

import platformdirs
from flask_socketio import SocketIO
from workforce import utils

# Relative imports to the server package modules
from .context import ServerContext
from . import queue as server_queue
from . import routes as server_routes
from . import sockets as server_sockets

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("werkzeug").setLevel(logging.WARNING)
log = logging.getLogger(__name__)


def stop_server(filename: str | None):
    if not filename:
        print("No file specified.")
        return

    abs_path = os.path.abspath(filename)
    registry = utils.clean_registry()

    if abs_path not in registry:
        log.warning(f"No active server found for '{filename}'")
        return

    entry = registry.pop(abs_path)
    utils.save_registry(registry)

    pid = entry.get("pid")
    port = entry.get("port")

    try:
        if platform.system() == "Windows":
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], check=False)
        else:
            os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        log.info("Server process %s already stopped.", pid)

    log.info(f"Stopped server for '{filename}' (PID {pid}) on port {port}")


def list_servers():
    registry = utils.clean_registry()
    if not registry:
        print("No active Workforce servers.")
        return

    print("Active Workforce servers:")
    for path, info in registry.items():
        print(f"  - {path}")
        print(f"    -> http://127.0.0.1:{info['port']} (PID {info['pid']}) clients={info.get('clients', 0)}")


def start_server(filename: str, port: int | None = None, background: bool = True):
    if not filename:
        sys.exit("No file specified")

    abs_path = os.path.abspath(filename)
    registry = utils.clean_registry()

    if abs_path in registry:
        log.info(f"Server for '{abs_path}' already running on port {registry[abs_path]['port']}")
        return

    if port is None:
        port = utils.find_free_port()

    # Background (fork) mode
    if background and sys.platform != "emscripten":
        cmd = [
            sys.executable,
            "-m", "workforce",
            "server", "start",
            abs_path,
            "--foreground",
            "--port", str(port)
        ]

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=os.getcwd(),
        )

        registry[abs_path] = {"port": port, "pid": process.pid, "clients": 0}
        utils.save_registry(registry)

        log.info(f"Server started for '{abs_path}' on port {port} with PID {process.pid}")
        return

    # Foreground server orchestration
    cache_dir = platformdirs.user_cache_dir("workforce")
    server_cache_dir = os.path.join(cache_dir, str(os.getpid()))
    os.makedirs(server_cache_dir, exist_ok=True)
    log.info(f"Caching requests to {server_cache_dir}")

    ctx = ServerContext(
        path=abs_path,
        port=port,
        server_cache_dir=server_cache_dir,
        mod_queue=queue.Queue(),
        socketio=None,
    )

    # Create app and socketio, attach to context
    from flask import Flask
    app = Flask(__name__)
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading", ping_interval=30, ping_timeout=90)
    ctx.socketio = socketio

    # Register routes and sockets
    server_routes.register_routes(app, ctx)
    server_sockets.register_socket_handlers(socketio, ctx)

    # Start the background graph worker
    server_queue.start_graph_worker(ctx)

    # Update registry
    registry[abs_path] = {"port": port, "pid": os.getpid(), "clients": 0}
    utils.save_registry(registry)

    log.info(f"Serving '{abs_path}' on http://127.0.0.1:{port}")

    try:
        socketio.run(app, port=port)
    finally:
        reg = utils.load_registry()
        reg.pop(abs_path, None)
        utils.save_registry(reg)
        log.info("Server shut down cleanly; registry updated.")


# CLI shims
def cmd_start(args):
    start_server(args.filename or utils.default_workfile(), port=args.port, background=not args.foreground)

def cmd_stop(args):
    stop_server(args.filename or utils.default_workfile())

def cmd_list(args):
    list_servers()
