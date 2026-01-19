import os
import platform
import signal
import subprocess
import urllib.request
import urllib.error
import urllib.parse
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
        
        # Clean up old caches to prevent unbounded disk growth
        _cycle_workspace_caches()
        
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
    """Destroy and cleanup a workspace context.
    
    Worker thread is not explicitly stopped - it will exit with the server process.
    """
    global _contexts
    
    # Get context but DON'T remove from registry yet
    with _contexts_lock:
        if workspace_id not in _contexts:
            return
        ctx = _contexts[workspace_id]
    
    # Clear EventBus subscriptions to prevent lingering references
    if hasattr(ctx, 'events') and ctx.events:
        # EventBus will be garbage collected, but explicitly clear subscriptions
        ctx.events._subscribers.clear()
        log.debug(f"Cleared EventBus subscriptions for {workspace_id}")
    
    # Clear run tracking
    ctx.active_runs.clear()
    ctx.active_node_run.clear()
    
    # Remove from registry
    with _contexts_lock:
        _contexts.pop(workspace_id, None)
    
    # Clean up workspace cache to prevent unbounded disk growth
    _clean_workspace_cache(workspace_id)
    
    log.info(f"Destroyed workspace context: {workspace_id}")


def _stop_nodes_for_workspace(workspace_id: str) -> dict:
    """Kill running processes for a workspace. Used by manual stop_server().
    
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


def _clean_workspace_cache(workspace_id: str):
    """Remove cache for a specific workspace."""
    root = _cache_root()
    path = os.path.join(root, workspace_id)
    try:
        if os.path.exists(path):
            shutil.rmtree(path, ignore_errors=True)
            log.debug(f"Cleaned cache for workspace {workspace_id}")
    except Exception as e:
        log.warning(f"Failed to remove cache for {workspace_id}: {e}")


def _cycle_workspace_caches(max_cache_size_mb: int = 500, max_age_days: int = 7):
    """Clean old or excess workspace caches to prevent unbounded disk growth.
    
    Removes:
    - Individual workspace caches older than max_age_days
    - Workspace caches when total size exceeds max_cache_size_mb (removes oldest first)
    """
    root = _cache_root()
    if not os.path.exists(root):
        return  # No cache to clean yet
    
    try:
        entries = []
        total_size = 0
        current_time = time.time()
        
        # Collect cache entries with size and mtime
        for entry in os.listdir(root):
            full_path = os.path.join(root, entry)
            if not os.path.isdir(full_path):
                continue
            
            try:
                # Get directory size
                size = sum(
                    os.path.getsize(os.path.join(dirpath, filename))
                    for dirpath, dirnames, filenames in os.walk(full_path)
                    for filename in filenames
                )
                mtime = os.path.getmtime(full_path)
                age_days = (current_time - mtime) / (24 * 3600)
                
                entries.append({
                    "name": entry,
                    "path": full_path,
                    "size": size,
                    "mtime": mtime,
                    "age_days": age_days
                })
                total_size += size
            except OSError:
                pass
        
        # Remove caches older than max_age_days
        for entry in entries:
            if entry["age_days"] > max_age_days:
                try:
                    shutil.rmtree(entry["path"], ignore_errors=True)
                    log.info(f"Removed old cache {entry['name']} (age: {entry['age_days']:.1f} days)")
                    total_size -= entry["size"]
                except Exception as e:
                    log.warning(f"Failed to remove old cache {entry['name']}: {e}")
        
        # If still over size limit, remove oldest caches
        max_size_bytes = max_cache_size_mb * 1024 * 1024
        if total_size > max_size_bytes:
            # Sort by mtime (oldest first)
            entries.sort(key=lambda x: x["mtime"])
            for entry in entries:
                if total_size <= max_size_bytes:
                    break
                try:
                    shutil.rmtree(entry["path"], ignore_errors=True)
                    log.info(f"Removed cache {entry['name']} to stay under size limit ({entry['size'] / 1024 / 1024:.1f} MB)")
                    total_size -= entry["size"]
                except Exception as e:
                    log.warning(f"Failed to remove cache {entry['name']}: {e}")
    except Exception as e:
        log.warning(f"Error cycling workspace caches: {e}")


def _clear_all_caches():
    """Remove all workspace caches. Used by manual stop_server()."""
    root = _cache_root()
    if not os.path.exists(root):
        return
    try:
        shutil.rmtree(root, ignore_errors=True)
        log.info("Cleared all workspace caches")
    except Exception as e:
        log.warning(f"Failed to clear workspace caches: {e}")


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
    
    # If PID file exists and process is NOT alive, clean it up
    if pid_info and not _pid_alive(pid_info[2]):
        try:
            os.remove(_pid_file())
        except OSError:
            pass
        pid_info = None  # Treat as no PID file now
    
    # If PID file exists and process IS alive, we're done
    if pid_info and _pid_alive(pid_info[2]):
        existing_host, existing_port, existing_pid = pid_info
        print(f"Server already running on http://{existing_host}:{existing_port} (pid {existing_pid})")
        return

    lock_acquired = True if skip_lock else _acquire_lock()
    if not lock_acquired:
        raise RuntimeError("Another server start is in progress or server already running")

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
            # Health check failed - but the port might still be in use
            # Fall through to port check below
            pass

    # Ensure host/port are available
    if is_port_in_use(port, host=host):
        # Port is in use. For background starts, just raise an error and let the caller handle it
        # (they can either wait for the server to start or use a different port)
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


def list_servers(server_url: str | None = None):
    """List active workspace contexts with connection URLs.
    
    When server_url is provided, query that endpoint directly (no PID checks).
    Otherwise, use PID file discovery; if no server is running, print guidance.
    """
    if server_url:
        host, port, base_url = utils._normalize_server_url(server_url)
        pid = 0
    else:
        pid_info = _read_pid_file()
        
        # Try PID file first
        if pid_info and _pid_alive(pid_info[2]):
            host, port, pid = pid_info
            base_url = f"http://{host}:{port}"
        else:
            # Clean up stale PID file
            if pid_info:
                try:
                    os.remove(_pid_file())
                except OSError:
                    pass
            
            # No server running on default port - offer to start one
            print("Server is not running.")
            print("Start the server with: wf server start")
            return

    try:
        import json
        import socket

        url = f"{base_url}/workspaces"
        with urllib.request.urlopen(url, timeout=2) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            workspaces = data.get("workspaces", [])
            server_info = data.get("server", {})

            if server_url:
                bind_host, bind_port = host, port
                local_ips = []
                bound_to_all = False
            else:
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
            if pid > 0:
                print(f"Workforce Server (pid {pid}) on port {bind_port}")
            else:
                print(f"Workforce Server on port {bind_port}")
            print("=" * 80)

            if server_url:
                print(f"\n📍 Access URL: {base_url}")
            elif bound_to_all and local_ips:
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

                if server_url:
                    print(f"  URL:       {base_url}/workspace/{ws_id}")
                elif bound_to_all and local_ips:
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
    list_servers(server_url=getattr(args, 'server_url', None))

