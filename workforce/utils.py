#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
utils.py — Shared Workforce utilities for workspace identification,
networking, and interacting with the fixed-port multi-tenant server.
"""

import hashlib
import json
import os
import socket
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import signal
import subprocess
import time

# -----------------------------------------------------------------------------
# Workspace identification
# -----------------------------------------------------------------------------

def compute_workspace_id(workfile_path: str) -> str:
    """Compute deterministic workspace ID from absolute Workfile path.
    
    Normalizes paths to handle cross-OS and network share compatibility:
    - Converts to absolute path
    - Normalizes separators to forward slashes
    - On Windows, strips drive letters for network paths (//server/share)
    - Resolves symlinks to canonical path
    
    Args:
        workfile_path: Path to the workflow file
    
    Returns:
        Workspace ID in format ws_<8-char-hash>
    """
    # Get absolute path
    abs_path = os.path.abspath(workfile_path)
    
    # Resolve symlinks to get canonical path
    try:
        abs_path = os.path.realpath(abs_path)
    except (OSError, ValueError):
        # If realpath fails (e.g., broken symlink), use abspath
        pass
    
    # Normalize path separators to forward slashes for cross-platform consistency
    normalized_path = abs_path.replace(os.sep, '/')
    
    # On Windows, handle network paths by stripping drive letters from UNC paths
    # \\server\share becomes //server/share for consistency
    if sys.platform == 'win32' and normalized_path.startswith('//'):
        # Already a UNC path, keep as-is
        pass
    elif sys.platform == 'win32' and len(normalized_path) > 1 and normalized_path[1] == ':':
        # Local drive path like C:/path - keep as-is for now
        # Could be enhanced to detect if it's a mapped network drive
        pass
    
    # Compute hash of normalized path
    path_bytes = normalized_path.encode("utf-8")
    hash_hex = hashlib.sha256(path_bytes).hexdigest()[:8]
    return f"ws_{hash_hex}"


def parse_workspace_url(url: str) -> tuple[str, str] | None:
    """
    Parse a workspace URL to extract server URL and workspace ID.
    
    Supports formats:
    - http://host:port/workspace/ws_abc123
    - http://host:port/workspace/ws_abc123/get-graph
    - host:port/workspace/ws_abc123
    
    Returns:
        (server_url, workspace_id) tuple or None if not a valid workspace URL
    """
    import re
    
    # Add http:// if missing
    if not url.startswith(('http://', 'https://')):
        url = 'http://' + url
    
    # Match pattern: http://host:port/workspace/ws_XXXXXXXX[/endpoint]
    # Workspace ID format: ws_ followed by 8+ alphanumeric characters
    pattern = r'^(https?://[^/]+)/workspace/(ws_[a-zA-Z0-9]{8,})(?:/.*)?$'
    match = re.match(pattern, url)
    
    if match:
        server_url = match.group(1)
        workspace_id = match.group(2)
        return (server_url, workspace_id)
    
    return None


def is_workspace_url(text: str) -> bool:
    """Check if text looks like a workspace URL."""
    return parse_workspace_url(text) is not None


def looks_like_url(text: str) -> bool:
    r"""Check if text looks like a URL (but may not be valid).
    
    Distinguishes URLs from Windows file paths (C:\...).
    """
    if not text:
        return False
    
    # Check for explicit URL schemes first
    if text.startswith(('http://', 'https://')):
        return True
    
    # Check for /workspace/ endpoint
    if '/workspace/' in text:
        return True
    
    # Check for colon, but exclude Windows drive letters (C:, D:, etc.)
    # Windows drive letters are single letters followed by colon at position 1
    if ':' in text:
        # If colon is at position 1 and text[0] is a single letter, it's a drive letter
        colon_pos = text.find(':')
        if colon_pos == 1 and text[0].isalpha():
            # This is a Windows drive letter path (C:\...) or relative path with colon
            # In URL context, we need host:port, so position 1 colon isn't a URL
            return False
        # Otherwise, it might be a URL with host:port
        return True
    
    return False


def get_workspace_url(workspace_id: str, endpoint: str = "") -> str:
    """Build absolute URL for a workspace endpoint.
    
    Discovers or starts the server via resolve_server().
    """
    server_url = resolve_server()
    base = f"{server_url}/workspace/{workspace_id}"
    if endpoint:
        if not endpoint.startswith("/"):
            endpoint = "/" + endpoint
        return base + endpoint
    return base

# -----------------------------------------------------------------------------
# HTTP POST helper
# -----------------------------------------------------------------------------

def _post(base_url: str, endpoint: str, payload: dict | None = None, retry_on_connect_error: bool = False) -> dict:
    """POST JSON payload to an endpoint. Used by edit, run, and GUI clients.
    
    If retry_on_connect_error=True, retry up to 30 times with 0.5s delay between attempts (15s total).
    This allows time for background server startup, especially on Windows frozen executables.
    """
    if not endpoint.startswith("/"):
        endpoint = "/" + endpoint

    url = f"{base_url.rstrip('/')}{endpoint}"
    data = json.dumps(payload or {}).encode("utf-8")

    max_retries = 30 if retry_on_connect_error else 1
    last_error = None
    
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            
            with urllib.request.urlopen(req) as resp:
                resp_data = resp.read().decode("utf-8")
                try:
                    return json.loads(resp_data)
                except json.JSONDecodeError:
                    raise RuntimeError(f"Server returned non-JSON response: {resp_data}")

        except urllib.error.HTTPError as e:
            # HTTP errors (404, 409, 500, etc.) - try to read error response
            try:
                error_body = e.read().decode("utf-8")
                error_data = json.loads(error_body)
                error_msg = error_data.get("error", str(e))
            except:
                error_msg = str(e)
            raise RuntimeError(f"Failed to POST to {url}: HTTP Error {e.code} {e.reason}. {error_msg}")
        
        except (urllib.error.URLError, ConnectionRefusedError, OSError) as e:
            # Connection errors - retry if enabled
            last_error = e
            if retry_on_connect_error and attempt < max_retries - 1:
                import time
                time.sleep(0.5)
                continue
            raise RuntimeError(f"Failed to POST to {url}: {e}")

        except Exception as e:
            raise RuntimeError(f"Unexpected error POSTing to {url}: {e}")
    
    raise RuntimeError(f"Failed to POST to {url} after {max_retries} retries: {last_error}")



def shell_quote_multiline(script: str) -> str:
    """Escape single quotes in shell scripts for safe execution."""
    return script.replace("'", "'\\''")


def default_workfile() -> str | None:
    """Return ./Workfile if it exists, else None."""
    path = os.path.join(os.getcwd(), "Workfile")
    return path if os.path.exists(path) else None


def get_absolute_path(path: str) -> str:
    """Convert relative or absolute path to absolute path."""
    return os.path.abspath(path)


def ensure_workfile(path: str | None = None) -> str:
    """Resolve a workfile path or create a temporary one when absent.

    Order of precedence:
    1) Explicit path provided
    2) ./Workfile if it exists
    3) New temp file path in the system temp directory (not pre-created)

    Returns an absolute path suitable for compute_workspace_id.
    """
    if path:
        return os.path.abspath(path)

    existing = default_workfile()
    if existing:
        return os.path.abspath(existing)

    fd, temp_path = tempfile.mkstemp(prefix="workforce_tmp_", suffix=".wf.graphml")
    os.close(fd)
    # Remove the empty file so the first load can create a valid GraphML
    try:
        os.unlink(temp_path)
    except FileNotFoundError:
        pass
    return temp_path


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Check if a port is in use.
    
    Args:
        port: Port number to check
        host: Host to bind to (default: 127.0.0.1)
    
    Returns:
        True if port is in use, False if available
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return False  # Port is free
        except OSError:
            return True  # Port is in use


def runtime_dir() -> str:
    """Return the directory used for runtime artifacts (~/.workforce)."""
    path = os.path.join(os.path.expanduser("~"), ".workforce")
    os.makedirs(path, exist_ok=True)
    return path


def pid_file_path() -> str:
    return os.path.join(runtime_dir(), "server.pid")


def lock_file_path() -> str:
    return os.path.join(runtime_dir(), "server.lock")


def log_file_path(log_dir: str | None = None) -> str:
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
        return os.path.join(log_dir, "server.log")
    return os.path.join(runtime_dir(), "server.log")


def _read_pid_file() -> tuple[str, int, int] | None:
    """Return (host, port, pid) if pid file exists and is parseable."""
    path = pid_file_path()
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]
        if len(lines) < 2:
            return None
        host_port = lines[0]
        if ":" not in host_port:
            return None
        host, port_str = host_port.split(":", 1)
        pid = int(lines[1])
        port = int(port_str)
        return host, port, pid
    except Exception:
        return None


def _pid_alive(pid: int) -> bool:
    """Check if a process with given PID is still alive.
    
    Handles both Unix and Windows platforms correctly:
    - Returns False if pid is 0 (invalid/unknown)
    - Unix: Uses os.kill(pid, 0) signal check
    - Windows: Uses tasklist with very aggressive timeout
    """
    if pid == 0:
        # Invalid or unknown PID
        return False
    
    try:
        if sys.platform != "win32":
            # Unix: os.kill(pid, 0) checks liveness without killing
            os.kill(pid, 0)
            return True
        else:
            # Windows: Use tasklist with extremely short timeout
            # tasklist can hang on some systems, so fail fast
            try:
                result = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {pid}"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=0.1
                )
                # tasklist returns 0 if process found, 1 if not
                return result.returncode == 0
            except subprocess.TimeoutExpired:
                # Timeout is likely due to tasklist hang on bad PID
                # Assume dead to speed up discovery
                return False
    except (PermissionError, ProcessLookupError):
        # PermissionError: process exists but we can't send signal (treat as alive)
        # ProcessLookupError: process doesn't exist
        return pid != 0 and sys.platform != "win32"
    except Exception:
        # Unknown error - assume dead to avoid false positives
        return False


def _normalize_server_url(url: str) -> tuple[str, int, str]:
    """Normalize URL, returning (host, port, normalized_url)."""
    if not url.startswith(("http://", "https://")):
        url = "http://" + url
    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 5000
    normalized = f"http://{host}:{port}"
    return host, port, normalized


def register_workspace(server_url: str, workfile_path: str) -> dict:
    """Register a workspace path with the server and return metadata.
    
    Retries up to 30 times with 0.5s delay (15s total) to wait for server startup.
    """
    return _post(server_url, "/workspace/register", {"path": workfile_path}, retry_on_connect_error=True)


def remove_workspace(server_url: str, workspace_id: str) -> dict:
    """Remove a workspace from the server."""
    import urllib.request
    url = f"{server_url.rstrip('/')}/workspace/{workspace_id}"
    req = urllib.request.Request(url, method="DELETE")
    with urllib.request.urlopen(req) as resp:
        data = resp.read().decode("utf-8")
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            return {"status": data}


def find_running_server(start_port: int = 5000, end_port: int = 5100) -> str | None:
    """Discover a running Workforce server by scanning ports for /workspaces endpoint.
    
    Scans the port range [start_port, end_port) for a responsive /workspaces endpoint.
    Returns the first responsive server's URL, or None if none found.
    
    This implements the documented "port scanning" discovery mechanism that works
    even when the PID file is missing or stale.
    
    Args:
        start_port: Start of port range to scan (default: 5000)
        end_port: End of port range (exclusive, default: 5100)
    
    Returns:
        Server URL like "http://127.0.0.1:5000" if found, else None
    """
    # Try a quick HTTP GET on the most common port first before full scan
    # This avoids slow port scanning in the common case of server on default port
    try:
        url = "http://127.0.0.1:5000"
        with urllib.request.urlopen(f"{url}/workspaces", timeout=0.1) as resp:
            if resp.status == 200:
                return url
    except Exception:
        pass
    
    # Full port scan only if default port failed
    # Use very aggressive timeout to avoid hanging when no server is running
    for port in range(start_port, end_port):
        if port == 5000:
            continue  # Already checked above
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.05)  # Extremely short timeout (50ms)
            result = sock.connect_ex(("127.0.0.1", port))
            sock.close()
            
            # If socket connected, verify with HTTP request
            if result == 0:
                url = f"http://127.0.0.1:{port}"
                try:
                    with urllib.request.urlopen(f"{url}/workspaces", timeout=0.1) as resp:
                        if resp.status == 200:
                            return url
                except Exception:
                    pass
        except Exception:
            pass
    
    return None


def resolve_server(server_url: str | None = None, start_if_missing: bool = True, log_dir: str | None = None) -> str:
    """Return server URL, starting the server if needed.

    Discovery strategy:
    1. Try the candidate port (explicit URL, env var, or default)
    2. Try PID file if different from candidate
    3. Start new server on candidate port if not found

    Priority: explicit server_url argument > WORKFORCE_SERVER_URL env > http://127.0.0.1:5000.
    
    Note: If server needs to be started, this function returns immediately.
    Callers should poll/wait for server availability if needed.
    """
    candidate = server_url or os.environ.get("WORKFORCE_SERVER_URL") or "http://127.0.0.1:5000"
    host, port, normalized = _normalize_server_url(candidate)

    # Step 1: Quick check on the candidate URL (the one we're supposed to use)
    try:
        with urllib.request.urlopen(f"{candidate}/workspaces", timeout=0.1) as resp:
            if resp.status == 200:
                return candidate
    except Exception:
        pass

    # Step 2: Try PID file lookup (fast path if PID file exists and process is alive)
    # Only check PID file if it points to a different location than our candidate
    pid_info = _read_pid_file()
    if pid_info:
        pid_host, pid_port, pid = pid_info
        pid_url = f"http://{pid_host}:{pid_port}"
        if pid_url != candidate:
            # Different server running - inform user
            if server_url:
                raise RuntimeError(
                    f"Server already running at {pid_url} (pid {pid}); requested {normalized}"
                )
            # Return the running server if no explicit URL was requested
            if _pid_alive(pid):
                return pid_url
        else:
            # Same URL in PID file, clean it up since it didn't respond
            try:
                os.remove(pid_file_path())
            except OSError:
                pass

    if not start_if_missing:
        raise RuntimeError("Workforce server is not running")

    from workforce.server import start_server

    # Step 3: Exponential backoff before starting new server to prevent concurrent starts
    # This allows a second wf command to find the server started by the first one
    for backoff_delay in [0.5, 1.0]:
        time.sleep(backoff_delay)
        # Quick recheck on candidate
        try:
            with urllib.request.urlopen(f"{candidate}/workspaces", timeout=0.1) as resp:
                if resp.status == 200:
                    return candidate
        except Exception:
            pass

    # Step 4: Start new server on candidate port
    start_server(background=True, host=host, port=port, log_dir=log_dir)

    # Return expected URL immediately - server will start in background
    return normalized


def get_running_server() -> tuple[str, int, int] | None:
    """Return (host, port, pid) if a server is running, else None.
    
    Uses PID file first (fast), falls back to port scanning if needed.
    """
    info = _read_pid_file()
    if info:
        host, port, pid = info
        if _pid_alive(pid):
            return info
        # PID file points to dead process, clean it up
        try:
            os.remove(pid_file_path())
        except OSError:
            pass
    
    # Fall back to port scanning
    discovered_url = find_running_server()
    if discovered_url:
        # Return parsed host/port from discovered URL (pid is unknown in this path)
        parsed = urllib.parse.urlparse(discovered_url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 5000
        # Return 0 as placeholder for pid since we don't have it
        return (host, port, 0)
    
    return None
