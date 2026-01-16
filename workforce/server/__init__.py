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
import atexit
import shutil
from logging.handlers import RotatingFileHandler

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

log = logging.getLogger(__name__)

# Global app and socketio instances (single server process)
_app = None
_socketio = None
_contexts: dict[str, ServerContext] = {}
_contexts_lock = threading.Lock()
_bind_host: str | None = None
_bind_port: int | None = None
_log_configured = False


def _setup_logging(log_dir: str | None = None):
    """Configure rotating file logging for server, Flask, and SocketIO."""
    global _log_configured
    if _log_configured:
        return

    log_path = utils.log_file_path(log_dir)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    handler = RotatingFileHandler(log_path, maxBytes=10 * 1024 * 1024, backupCount=5)
    handler.setFormatter(formatter)
    handler.setLevel(logging.INFO)

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # Avoid duplicate handlers if re-imported
    existing_paths = [getattr(h, 'baseFilename', None) for h in root.handlers]
    if log_path not in existing_paths:
        root.addHandler(handler)

    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    logging.getLogger("werkzeug.serving").setLevel(logging.CRITICAL)
    _log_configured = True


def _pid_file() -> str:
    return utils.pid_file_path()


def _lock_file() -> str:
    return utils.lock_file_path()


def _write_pid_file(host: str, port: int, pid: int):
    path = _pid_file()
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"{host}:{port}\n{pid}\n")


def _read_pid_file() -> tuple[str, int, int] | None:
    return utils._read_pid_file()


def _pid_alive(pid: int) -> bool:
    return utils._pid_alive(pid)


def _acquire_lock() -> bool:
    """Acquire start lock to avoid racing starts. Returns True if lock acquired.
    
    Cleans up stale lock files older than 30 seconds before attempting to acquire.
    """
    path = _lock_file()
    
    # Clean up stale lock file (older than 30 seconds)
    if os.path.exists(path):
        try:
            mtime = os.path.getmtime(path)
            if time.time() - mtime > 30:
                os.remove(path)
        except (OSError, IOError):
            pass
    
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
        return True
    except FileExistsError:
        return False


def _release_lock():
    try:
        os.remove(_lock_file())
    except OSError:
        pass


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


def get_bind_info() -> tuple[str | None, int | None]:
    """Return the host and port the server believes it is bound to."""
    return _bind_host, _bind_port


def get_or_create_context(workspace_id: str, workfile_path: str, increment_client: bool = True) -> ServerContext:
    """Get existing context or create a new one for the workspace.
    
    Args:
        workspace_id: Unique identifier for the workspace
        workfile_path: Path to the workflow file
        increment_client: If True, increment client count under lock (default: True)
    
    Returns:
        ServerContext for the workspace
    """
    global _contexts, _socketio
    
    with _contexts_lock:
        if workspace_id in _contexts:
            ctx = _contexts[workspace_id]
            if increment_client:
                ctx.increment_clients()
            return ctx
        
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
        
        # Initialize client count if incrementing
        if increment_client:
            ctx.increment_clients()
        
        _contexts[workspace_id] = ctx
        log.info(f"Created workspace context: {workspace_id} for {workfile_path} (clients: {ctx.client_count})")
    
    # Register handlers and start worker AFTER releasing lock to avoid deadlock
    # Register event handlers for this workspace
    server_sockets.register_event_handlers(ctx)
    
    # Start the worker thread for this context
    start_graph_worker(ctx)
    
    return ctx


def destroy_context(workspace_id: str):
    """Destroy and cleanup a workspace context."""
    global _contexts
    
    # Get context but DON'T remove from registry yet
    with _contexts_lock:
        if workspace_id not in _contexts:
            return
        ctx = _contexts[workspace_id]
    
    # Stop worker FIRST (outside lock to avoid deadlock)
    # This ensures worker fully stops before context removed from registry
    if ctx.worker_thread and ctx.worker_thread.is_alive():
        log.info(f"Stopping worker thread for {workspace_id}")
        # Signal queue to stop (None sentinel)
        ctx.mod_queue.put(None)
        
        # Wait for thread with increased timeout (10s instead of 5s)
        # Slow CI systems may need more time for graceful shutdown
        ctx.worker_thread.join(timeout=10)
        
        if ctx.worker_thread.is_alive():
            log.error(f"Worker thread for {workspace_id} did not stop within 10 seconds - may be stuck in I/O or deadlocked")
            # Thread will become orphaned but at least we warned about it
            # In production, could consider thread.daemon=True or more aggressive termination
        else:
            log.info(f"Worker thread for {workspace_id} stopped cleanly")
    
    # Clear EventBus subscriptions to prevent lingering references
    if hasattr(ctx, 'events') and ctx.events:
        # EventBus will be garbage collected, but explicitly clear subscriptions
        ctx.events._subscribers.clear()
        log.debug(f"Cleared EventBus subscriptions for {workspace_id}")
    
    # Clear run tracking
    ctx.active_runs.clear()
    ctx.active_node_run.clear()
    
    # NOW remove from registry (AFTER worker stopped and cleanup complete)
    # This ensures registry accurately reflects cleanup state
    with _contexts_lock:
        _contexts.pop(workspace_id, None)
    
    _clear_workspace_cache(workspace_id)
    
    log.info(f"Destroyed workspace context: {workspace_id}")


def _stop_nodes_for_workspace(workspace_id: str) -> dict:
    """Kill running processes for a workspace. Extracted logic from routes /stop endpoint.
    
    Returns:
        dict with keys: killed (count), errors (list), stopped_nodes (list)
    """
    from workforce import edit
    
    ctx = get_context(workspace_id)
    if not ctx:
        return {"killed": 0, "errors": [], "stopped_nodes": []}
    
    try:
        G = edit.load_graph(ctx.workfile_path)
        running_nodes = []
        killed = 0
        errors = []

        # Attempt to kill processes for nodes marked as running
        for node_id, attrs in G.nodes(data=True):
            if attrs.get("status") == "running":
                running_nodes.append(node_id)
                pid_raw = attrs.get("pid", "")
                pid_str = str(pid_raw).strip() if pid_raw is not None else ""
                if pid_str.isdigit():
                    try:
                        os.kill(int(pid_str), signal.SIGKILL)
                        killed += 1
                    except Exception as e:
                        errors.append(f"{node_id}:{pid_str}:{e}")

        # Mark all running nodes as failed (enqueue through worker)
        for node_id in running_nodes:
            run_id = ctx.active_node_run.get(node_id)
            ctx.enqueue_status(ctx.workfile_path, "node", node_id, "fail", run_id)

        return {"killed": killed, "errors": errors, "stopped_nodes": running_nodes}
    except Exception as e:
        log.exception(f"Error stopping nodes for {workspace_id}")
        return {"killed": 0, "errors": [str(e)], "stopped_nodes": []}


def _cache_root() -> str:
    return platformdirs.user_cache_dir("workforce")


def _clear_workspace_cache(workspace_id: str):
    root = _cache_root()
    path = os.path.join(root, workspace_id)
    try:
        if os.path.exists(path):
            shutil.rmtree(path, ignore_errors=True)
    except Exception as e:
        log.warning(f"Failed to remove cache for {workspace_id}: {e}")


def _clear_all_caches():
    root = _cache_root()
    if not os.path.exists(root):
        return
    try:
        for entry in os.listdir(root):
            full = os.path.join(root, entry)
            if os.path.isdir(full):
                shutil.rmtree(full, ignore_errors=True)
    except Exception as e:
        log.warning(f"Failed to clear workspace caches: {e}")


def graceful_shutdown():
    """Stop all running processes and exit the server gracefully."""
    log.info("========== GRACEFUL SERVER SHUTDOWN ==========")
    log.info("Stopping all running nodes across all workspaces...")
    
    with _contexts_lock:
        workspace_ids = list(_contexts.keys())
    
    # Stop all running nodes in each workspace
    total_killed = 0
    for workspace_id in workspace_ids:
        log.info(f"Stopping nodes for workspace: {workspace_id}")
        result = _stop_nodes_for_workspace(workspace_id)
        total_killed += result["killed"]
        if result["errors"]:
            log.warning(f"Errors stopping {workspace_id}: {result['errors']}")
        log.info(f"Workspace {workspace_id}: killed {result['killed']} processes, stopped {len(result['stopped_nodes'])} nodes")
    
    log.info(f"Total processes killed: {total_killed}")
    log.info("Exiting server process...")
    
    # Stop socketio if it's running (skip if not in request context)
    if _socketio:
        try:
            _socketio.stop()
        except RuntimeError as e:
            # Ignore "Working outside of request context" errors
            if "Working outside of request context" not in str(e):
                log.warning(f"Error stopping socketio: {e}")
        except Exception as e:
            log.warning(f"Error stopping socketio: {e}")

    try:
        os.remove(_pid_file())
    except OSError:
        pass
    _release_lock()
    _clear_all_caches()

    # Exit the process
    os._exit(0)


def _signal_handler(signum, frame):
    """Handle shutdown signals (SIGTERM, SIGINT)."""
    sig_name = signal.Signals(signum).name
    log.info(f"Received signal {sig_name} ({signum}), triggering graceful shutdown")
    # Call graceful_shutdown directly to kill processes and exit
    graceful_shutdown()


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


def start_server(background: bool = True, host: str = "127.0.0.1", port: int = 5000, log_dir: str | None = None):
    """Start the single machine-wide server with explicit host/port.
    
    Environment variable precedence:
    - Server binds to WORKFORCE_HOST (if set) or host parameter
    - Server binds to WORKFORCE_PORT (if set) or port parameter
    - Health checks use WORKFORCE_URL (if set), else derive from host/port
    - Logs written to WORKFORCE_LOG_DIR (if set) or log_dir parameter
    """

    log_dir = log_dir or os.environ.get("WORKFORCE_LOG_DIR")
    skip_lock = os.environ.get("WORKFORCE_SKIP_LOCK", "0") in ("1", "true", "True")
    pid_info = _read_pid_file()
    if pid_info and _pid_alive(pid_info[2]):
        existing_host, existing_port, existing_pid = pid_info
        print(f"Server already running on http://{existing_host}:{existing_port} (pid {existing_pid})")
        return

    lock_acquired = True if skip_lock else _acquire_lock()
    if not lock_acquired:
        raise RuntimeError("Another server start is in progress or server already running")

    # Clear stale pid file if present
    if pid_info and not _pid_alive(pid_info[2]):
        try:
            os.remove(_pid_file())
        except OSError:
            pass

    # Only setup logging in foreground mode to avoid concurrent file access
    if not background:
        _setup_logging(log_dir)

    # Check if server already running via HTTP health check
    if background:
        check_url = os.environ.get("WORKFORCE_URL")
        if not check_url:
            check_url = f"http://{host}:{port}"
        
        try:
            with urllib.request.urlopen(f"{check_url}/workspaces", timeout=2) as resp:
                if resp.status == 200:
                    print(f"Server already running on {check_url}")
                    _release_lock()
                    return
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
            # No server running, proceed with start
            pass

    # Ensure host/port are available
    if is_port_in_use(port, host=host):
        _release_lock()
        raise RuntimeError(f"Port {port} on {host} is already in use")

    if background and sys.platform != "emscripten":
        env = os.environ.copy()
        env["WORKFORCE_SKIP_LOCK"] = "1"
        if log_dir:
            env["WORKFORCE_LOG_DIR"] = log_dir

        import workforce
        package_root = os.path.dirname(os.path.dirname(os.path.abspath(workforce.__file__)))
        pythonpath = env.get('PYTHONPATH', '')
        if package_root not in pythonpath.split(os.pathsep):
            env['PYTHONPATH'] = f"{package_root}{os.pathsep}{pythonpath}" if pythonpath else package_root

        cmd = [sys.executable, "-m", "workforce", "server", "start", "--foreground", "--host", host, "--port", str(port)]
        if log_dir:
            cmd += ["--log-dir", log_dir]

        print(f"Starting background server: {' '.join(cmd)}")
        
        # On Windows, detach subprocess from parent console to avoid signal propagation
        creation_flags = 0
        if sys.platform == "win32":
            creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=os.getcwd(),
            env=env,
            creationflags=creation_flags,
        )

        # Wait for server to be ready with HTTP health check (10 second timeout)
        print(f"Starting background server on http://{host}:{port}")
        server_url = f"http://{host}:{port}"
        start_time = time.time()
        timeout = 10
        
        while time.time() - start_time < timeout:
            try:
                with urllib.request.urlopen(f"{server_url}/workspaces", timeout=1) as resp:
                    if resp.status == 200:
                        print(f"Server is ready")
                        _release_lock()
                        return
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
                # Server not ready yet, continue waiting
                pass
            time.sleep(0.2)
        
        # Timeout waiting for server to start
        _release_lock()
        raise RuntimeError(f"Background server failed to start within {timeout} seconds")

    # Foreground server
    app, socketio = get_app()

    global _bind_host, _bind_port
    _bind_host, _bind_port = host, port

    _write_pid_file(host, port, os.getpid())

    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    log.info(f"Starting Workforce server on http://{host}:{port}")
    log.info("Server ready. Waiting for client connections...")

    try:
        socketio.run(app, host=host, port=port, allow_unsafe_werkzeug=True)
    except KeyboardInterrupt:
        log.info("Server interrupted, triggering graceful shutdown...")
        graceful_shutdown()
    finally:
        _release_lock()
        log.info("Server shutdown complete.")


def stop_server():
    """Stop the server via PID file, clear caches, and preserve logs."""

    pid_info = _read_pid_file()
    if not pid_info:
        print("No server registered. Use 'wf server start' to launch a server.")
        _clear_all_caches()
        _release_lock()
        return

    host, port, pid = pid_info
    if not _pid_alive(pid):
        log.info("Server pid not alive; cleaning up artifacts")
        try:
            os.remove(_pid_file())
        except OSError:
            pass
        _clear_all_caches()
        _release_lock()
        return

    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/PID", str(pid)], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            os.kill(pid, signal.SIGTERM)
        log.info(f"Sent termination signal to server pid {pid}")
    except Exception as e:
        log.warning(f"Failed to signal server pid {pid}: {e}")

    # Wait briefly for shutdown
    for _ in range(20):
        time.sleep(0.25)
        if not _pid_alive(pid):
            break

    if _pid_alive(pid):
        log.warning(f"Server pid {pid} is still alive after SIGTERM")
    else:
        log.info("Server stopped")

    try:
        os.remove(_pid_file())
    except OSError:
        pass
    _release_lock()
    _clear_all_caches()


def list_servers():
    """List active workspace contexts with connection URLs."""
    pid_info = _read_pid_file()
    if not pid_info or not _pid_alive(pid_info[2]):
        print("Server is not running.")
        print("Start the server with: wf server start")
        return

    host, port, pid = pid_info

    try:
        import json
        import socket

        url = f"http://{host}:{port}/workspaces"
        with urllib.request.urlopen(url, timeout=2) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            workspaces = data.get("workspaces", [])
            server_info = data.get("server", {})
            bind_host = server_info.get("host") or host
            bind_port = int(server_info.get("port") or port)
            lan_enabled = bool(server_info.get("lan_enabled", bind_host not in ("127.0.0.1", "localhost")))

            local_ips = []
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
                s.close()
                if ip != '127.0.0.1' and not ip.startswith('127.'):
                    local_ips.append(ip)
            except:
                pass

            bound_to_all = lan_enabled or bind_host in ("0.0.0.0", "::", "0:0:0:0:0:0:0:0")

            print("=" * 80)
            print(f"Workforce Server (pid {pid}) on port {bind_port}")
            print("=" * 80)

            if bound_to_all and local_ips:
                print("\n📍 Access URLs:")
                print(f"  Local:    http://127.0.0.1:{bind_port}")
                for ip in local_ips:
                    print(f"  LAN:      http://{ip}:{bind_port}")
            else:
                print(f"\n📍 Access URL: http://{host}:{bind_port}")
                if not bound_to_all:
                    print("   ⚠️  Server bound to localhost only (not accessible from LAN)")
                    print(f"   To enable LAN access: wf server stop && wf server start --host 0.0.0.0")

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

                if bound_to_all and local_ips:
                    print("  URLs:")
                    print(f"    Local:   http://127.0.0.1:{bind_port}/workspace/{ws_id}")
                    for ip in local_ips:
                        print(f"    LAN:     http://{ip}:{bind_port}/workspace/{ws_id}")
                else:
                    print(f"  URL:       http://{host}:{bind_port}/workspace/{ws_id}")

            print("\n" + "=" * 80)

    except Exception as e:
        print(f"Error communicating with server: {e}")


# CLI shims
def cmd_start(args):
    # Default to background mode, unless --foreground is specified
    foreground = getattr(args, 'foreground', False)
    host = getattr(args, 'host', '127.0.0.1')
    port = getattr(args, 'port', 5000)
    log_dir = getattr(args, 'log_dir', None)
    try:
        start_server(background=not foreground, host=host, port=port, log_dir=log_dir)
    except KeyboardInterrupt:
        # User interrupted or Windows file operation interrupted - server may have started
        pass

def cmd_stop(args):
    stop_server()

def cmd_list(args):
    list_servers()

