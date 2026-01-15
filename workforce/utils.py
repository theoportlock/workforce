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
    """Check if text looks like a URL (but may not be valid)."""
    if not text:
        return False
    return (
        text.startswith(('http://', 'https://')) or 
        ':' in text or 
        '/workspace/' in text
    )


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

def _post(base_url: str, endpoint: str, payload: dict | None = None) -> dict:
    """POST JSON payload to an endpoint. Used by edit, run, and GUI clients."""
    if not endpoint.startswith("/"):
        endpoint = "/" + endpoint

    url = f"{base_url.rstrip('/')}{endpoint}"
    data = json.dumps(payload or {}).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
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
    
    except urllib.error.URLError as e:
        raise RuntimeError(f"Failed to POST to {url}: {e}")

    except Exception as e:
        raise RuntimeError(f"Unexpected error POSTing to {url}: {e}")


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


def is_port_in_use(port: int) -> bool:
    """Check if a port is in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("localhost", port))
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
    try:
        # On Unix, os.kill(pid, 0) checks liveness without killing
        if sys.platform != "win32":
            os.kill(pid, 0)
            return True
        # On Windows, os.kill may raise PermissionError for running processes
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except ProcessLookupError:
        return False
    except OSError:
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
    """Register a workspace path with the server and return metadata."""
    return _post(server_url, "/workspace/register", {"path": workfile_path})


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


def resolve_server(server_url: str | None = None, start_if_missing: bool = True, log_dir: str | None = None) -> str:
    """Return server URL, starting the server if needed.

    Priority: explicit server_url argument > WORKFORCE_SERVER_URL env > http://127.0.0.1:5000.
    """
    candidate = server_url or os.environ.get("WORKFORCE_SERVER_URL") or "http://127.0.0.1:5000"
    host, port, normalized = _normalize_server_url(candidate)

    pid_info = _read_pid_file()
    if pid_info:
        pid_host, pid_port, pid = pid_info
        if _pid_alive(pid):
            # If a running server exists but host/port differ, respect the running one
            if (pid_host, pid_port) != (host, port) and server_url:
                raise RuntimeError(
                    f"Server already running at http://{pid_host}:{pid_port} (pid {pid}); requested {normalized}"
                )
            return f"http://{pid_host}:{pid_port}"

    if not start_if_missing:
        raise RuntimeError("Workforce server is not running")

    from workforce.server import start_server

    start_server(background=True, host=host, port=port, log_dir=log_dir)

    # After start, trust the requested host/port; pid file should be created soon after
    return normalized


def get_running_server() -> tuple[str, int, int] | None:
    """Return (host, port, pid) if a server is running, else None."""
    info = _read_pid_file()
    if info and _pid_alive(info[2]):
        return info
    return None
