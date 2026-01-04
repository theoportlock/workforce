import os
import platform
import signal
import subprocess
import time
import socket
import sys
import logging
import threading

import platformdirs
from flask import Flask
from flask_socketio import SocketIO
from workforce import utils

# Rename to avoid conflict with local queue.py
import queue as std_queue

# Relative imports to the server package modules
from .context import ServerContext
from .queue import start_graph_worker
from . import routes as server_routes
from . import sockets as server_sockets

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("werkzeug").setLevel(logging.ERROR)
logging.getLogger("werkzeug.serving").setLevel(logging.CRITICAL)
log = logging.getLogger(__name__)

# Global app and socketio instances (single server process)
_app = None
_socketio = None
_contexts: dict[str, ServerContext] = {}
_contexts_lock = threading.Lock()


def get_app():
    """Lazy initialization of Flask app."""
    global _app, _socketio
    if _app is None:
        _app = Flask(__name__)
        _socketio = SocketIO(_app, cors_allowed_origins="*", async_mode="threading", 
                            ping_interval=30, ping_timeout=90)
        
        # Register route handlers with the shared app
        server_routes.register_routes(_app)
        
        # Register socket handlers
        server_sockets.register_socket_handlers(_socketio)
    
    return _app, _socketio


def get_or_create_context(workspace_id: str, workfile_path: str) -> ServerContext:
    """Get existing context or create a new one for the workspace."""
    global _contexts, _socketio
    
    with _contexts_lock:
        if workspace_id in _contexts:
            return _contexts[workspace_id]
        
        # Create new context
        cache_dir = platformdirs.user_cache_dir("workforce")
        workspace_cache_dir = os.path.join(cache_dir, workspace_id)
        os.makedirs(workspace_cache_dir, exist_ok=True)
        
        _, _socketio = get_app()
        
        ctx = ServerContext(
            workspace_id=workspace_id,
            workfile_path=workfile_path,
            server_cache_dir=workspace_cache_dir,
            mod_queue=std_queue.Queue(),
            socketio=_socketio,
        )
        
        # Register event handlers for this workspace
        server_sockets.register_event_handlers(ctx)
        
        # Start the worker thread for this context
        start_graph_worker(ctx)
        
        _contexts[workspace_id] = ctx
        log.info(f"Created workspace context: {workspace_id} for {workfile_path}")
        
        return ctx


def destroy_context(workspace_id: str):
    """Destroy and cleanup a workspace context."""
    global _contexts
    
    with _contexts_lock:
        if workspace_id not in _contexts:
            return
        
        ctx = _contexts.pop(workspace_id)
        
        # Stop worker if running
        if ctx.worker_thread and ctx.worker_thread.is_alive():
            # Signal queue to stop (empty queue = worker exits)
            ctx.mod_queue.put(None)
            ctx.worker_thread.join(timeout=2)
        
        # Clear run tracking
        ctx.active_runs.clear()
        ctx.active_node_run.clear()
        
        log.info(f"Destroyed workspace context: {workspace_id}")


def get_context(workspace_id: str) -> ServerContext | None:
    """Retrieve existing context, do not create."""
    with _contexts_lock:
        return _contexts.get(workspace_id)


def is_port_in_use(port: int) -> bool:
    """Check if a port is already in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def start_server(background: bool = True):
    """
    Start the single machine-wide server on fixed port.
    Fail fast if port is unavailable.
    
    Args:
        background: If True, spawn subprocess. If False, run foreground.
    """
    port = utils.WORKSPACE_SERVER_PORT
    
    # Check if port is already in use
    if is_port_in_use(port):
        # Port in use; if background=True, assume compatible server already running
        # If foreground, fail fast
        if not background:
            raise RuntimeError(f"Port {port} is already in use. Cannot start server.")
        log.info(f"Port {port} already in use; assuming compatible server is running.")
        return
    
    if background and sys.platform != "emscripten":
        # Spawn background server subprocess
        cmd = [sys.executable, "-m", "workforce", "server", "start", "--foreground"]
        log.info(f"Starting background server: {' '.join(cmd)}")
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=os.getcwd(),
        )
        
        # Wait for port to become available
        max_retries = 10
        for attempt in range(max_retries):
            time.sleep(0.5)
            if is_port_in_use(port):
                log.info(f"Server started on port {port} (PID {process.pid})")
                return
        
        # If we get here, server didn't start
        log.error("Server failed to start within timeout")
        process.terminate()
        raise RuntimeError("Failed to start server")
    
    # Foreground server
    app, socketio = get_app()
    
    log.info(f"Starting Workforce server on http://localhost:{port}")
    log.info("Server ready. Waiting for client connections...")
    
    try:
        socketio.run(app, host="127.0.0.1", port=port, allow_unsafe_werkzeug=True)
    except KeyboardInterrupt:
        log.info("Server shutting down...")
    finally:
        log.info("Server shutdown complete.")


def stop_server():
    """Stop the machine-wide server (sends SIGTERM to process)."""
    import os
    import signal
    import subprocess
    
    if not is_port_in_use(utils.WORKSPACE_SERVER_PORT):
        log.warning(f"No server found on port {utils.WORKSPACE_SERVER_PORT}")
        return
    
    # Find process listening on port 5000
    try:
        result = subprocess.run(
            ["lsof", "-i", f":{utils.WORKSPACE_SERVER_PORT}", "-t"],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.stdout.strip():
            pids = result.stdout.strip().split("\n")
            for pid_str in pids:
                try:
                    pid = int(pid_str)
                    os.kill(pid, signal.SIGTERM)
                    log.info(f"Sent SIGTERM to process {pid}")
                except (ValueError, ProcessLookupError, PermissionError) as e:
                    log.warning(f"Failed to kill PID {pid_str}: {e}")
        else:
            log.warning("Could not find PID for server process")
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        log.warning(f"Could not determine server PID (lsof error): {e}")
        # Fallback: try pkill
        try:
            subprocess.run(["pkill", "-f", "workforce server start"], timeout=2)
            log.info("Sent pkill signal to workforce server")
        except Exception as e2:
            log.error(f"Failed to stop server: {e2}")


def list_servers():
    """List active workspace contexts (diagnostic)."""
    # Try to fetch from server's /workspaces endpoint
    try:
        import urllib.request
        import json
        url = "http://localhost:5000/workspaces"
        with urllib.request.urlopen(url, timeout=2) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            workspaces = data.get("workspaces", [])
            if not workspaces:
                print("No active workspaces on server.")
                return
            print("Active workspaces:")
            for ws in workspaces:
                print(f"  - {ws['workspace_id']}: {ws['workfile_path']} ({ws['client_count']} clients)")
    except urllib.error.URLError as e:
        print("Server is not running.")
        print("Start the server with: wf server start")
    except Exception as e:
        print(f"Error communicating with server: {e}")


# CLI shims
def cmd_start(args):
    # Default to background mode, unless --foreground is specified
    foreground = getattr(args, 'foreground', False)
    start_server(background=not foreground)

def cmd_stop(args):
    stop_server()

def cmd_list(args):
    list_servers()

