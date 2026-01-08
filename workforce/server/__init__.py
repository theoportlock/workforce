import os
import platform
import signal
import subprocess
import urllib.request
import urllib.error
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


def is_port_in_use(port: int, host: str = "0.0.0.0") -> bool:
    """Check if a port is already in use on any interface."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return False  # Port is free
        except OSError:
            return True  # Port is in use


def _is_compatible_server(host: str, port: int) -> bool:
    """Check whether something listening on the port looks like a Workforce server."""
    url = f"http://{host}:{port}/workspaces"
    try:
        with urllib.request.urlopen(url, timeout=1) as resp:
            if resp.status != 200:
                return False
            # Basic schema check
            import json
            data = json.loads(resp.read().decode("utf-8"))
            return "workspaces" in data
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError, TimeoutError):
        return False


def start_server(background: bool = True, host: str = "0.0.0.0"):
    """
    Start the single machine-wide server with dynamic port discovery.
    
    Args:
        background: If True, spawn subprocess. If False, run foreground.
        host: Host to bind to (default: 0.0.0.0, accessible from all interfaces).
    """
    # Find a free port
    port = utils.find_free_port()
    log.info(f"Found free port: {port}")
    
    if background and sys.platform != "emscripten":
        # Ensure workforce package is in PYTHONPATH for subprocess
        env = os.environ.copy()
        
        # Find the parent directory containing the workforce package
        import workforce
        package_root = os.path.dirname(os.path.dirname(os.path.abspath(workforce.__file__)))
        
        # Add to PYTHONPATH if not already there
        pythonpath = env.get('PYTHONPATH', '')
        if package_root not in pythonpath.split(os.pathsep):
            env['PYTHONPATH'] = f"{package_root}{os.pathsep}{pythonpath}" if pythonpath else package_root
        
        # Spawn background server subprocess with host argument
        cmd = [sys.executable, "-m", "workforce", "server", "start", "--foreground", "--host", host]
        log.info(f"Starting background server: {' '.join(cmd)}")
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=os.getcwd(),
            env=env,
        )
        
        # Wait for server to be discoverable via health check
        max_retries = 10
        for attempt in range(max_retries):
            time.sleep(0.5)
            result = utils.find_running_server(host="127.0.0.1")  # Always check localhost for discovery
            if result:
                found_host, found_port = result
                log.info(f"Server started on {found_host}:{found_port} (PID {process.pid})")
                return
        
        # If we get here, server didn't start
        log.error("Server failed to start within timeout")
        process.terminate()
        raise RuntimeError("Failed to start server")
    
    # Foreground server
    app, socketio = get_app()
    
    log.info(f"Starting Workforce server on http://{host}:{port}")
    log.info("Server ready. Waiting for client connections...")
    
    try:
        socketio.run(app, host=host, port=port, allow_unsafe_werkzeug=True)
    except KeyboardInterrupt:
        log.info("Server shutting down...")
    finally:
        log.info("Server shutdown complete.")


def stop_server():
    """Stop the machine-wide server (sends SIGTERM to process)."""
    import os
    import signal
    import subprocess
    
    # Find running server
    result = utils.find_running_server()
    if not result:
        log.warning("No Workforce server found running")
        return
    
    found_host, found_port = result
    
    # Find process listening on discovered port
    try:
        result = subprocess.run(
            ["lsof", "-i", f":{found_port}", "-t"],
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
            log.warning(f"Could not find PID for server process on port {found_port}")
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        log.warning(f"Could not determine server PID (lsof error): {e}")
        # Fallback: try pkill
        try:
            subprocess.run(["pkill", "-f", "workforce server start"], timeout=2)
            log.info("Sent pkill signal to workforce server")
        except Exception as e2:
            log.error(f"Failed to stop server: {e2}")


def list_servers():
    """List active workspace contexts with connection URLs."""
    # Find running server
    result = utils.find_running_server()
    if not result:
        print("Server is not running.")
        print("Start the server with: wf server start")
        return
    
    found_host, found_port = result
    
    # Try to fetch from server's /workspaces endpoint
    try:
        import urllib.request
        import json
        import socket
        
        url = f"http://{found_host}:{found_port}/workspaces"
        with urllib.request.urlopen(url, timeout=2) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            workspaces = data.get("workspaces", [])
            
            # Get local network interfaces
            local_ips = []
            try:
                # Get the primary network interface IP (most reliable method)
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))  # Doesn't actually send data
                ip = s.getsockname()[0]
                s.close()
                if ip != '127.0.0.1' and not ip.startswith('127.'):
                    local_ips.append(ip)
            except:
                pass
            
            # Check what interface the server is bound to
            try:
                import subprocess
                netstat_output = subprocess.run(
                    ["ss", "-tlnp"], 
                    capture_output=True, 
                    text=True, 
                    timeout=1
                ).stdout
                
                # Look for the port binding
                bound_to_all = f"0.0.0.0:{found_port}" in netstat_output or f"*:{found_port}" in netstat_output
            except:
                bound_to_all = False
            
            # Display server info
            print("=" * 80)
            print(f"Workforce Server on port {found_port}")
            print("=" * 80)
            
            if bound_to_all and local_ips:
                print("\n📍 Access URLs:")
                print(f"  Local:    http://127.0.0.1:{found_port}")
                for ip in local_ips:
                    print(f"  LAN:      http://{ip}:{found_port}")
            else:
                print(f"\n📍 Access URL: http://{found_host}:{found_port}")
                if not bound_to_all:
                    print("   ⚠️  Server bound to localhost only (not accessible from LAN)")
                    print(f"   To enable LAN access: wf server stop && wf server start --host 0.0.0.0")
            
            # Display workspaces
            if not workspaces:
                print("\n📂 No active workspaces")
                print("   Open a workflow with: wf gui")
                return
                
            print(f"\n📂 Active Workspaces ({len(workspaces)}):")
            print("-" * 80)
            
            for ws in workspaces:
                ws_id = ws['workspace_id']
                ws_path = ws['workfile_path']
                client_count = ws['client_count']
                
                print(f"\n  Workspace: {ws_id}")
                print(f"  File:      {ws_path}")
                print(f"  Clients:   {client_count}")
                
                # Show connection URLs
                if bound_to_all and local_ips:
                    print(f"  URLs:")
                    print(f"    Local:   http://127.0.0.1:{found_port}/workspace/{ws_id}")
                    for ip in local_ips:
                        print(f"    LAN:     http://{ip}:{found_port}/workspace/{ws_id}")
                else:
                    print(f"  URL:       http://{found_host}:{found_port}/workspace/{ws_id}")
            
            print("\n" + "=" * 80)
            
    except Exception as e:
        print(f"Error communicating with server: {e}")


# CLI shims
def cmd_start(args):
    # Default to background mode, unless --foreground is specified
    foreground = getattr(args, 'foreground', False)
    host = getattr(args, 'host', '0.0.0.0')
    start_server(background=not foreground, host=host)

def cmd_stop(args):
    stop_server()

def cmd_list(args):
    list_servers()

