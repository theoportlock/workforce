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
import urllib.request

# Workspace server configuration (dynamic port via find_free_port)
WORKSPACE_SERVER_URL = "http://localhost:5000"  # Deprecated: use resolve_server() instead
WORKSPACE_SERVER_PORT = 5000  # Deprecated: use find_free_port() instead

# -----------------------------------------------------------------------------
# Workspace identification
# -----------------------------------------------------------------------------

def compute_workspace_id(workfile_path: str) -> str:
    """Compute deterministic workspace ID from absolute Workfile path."""
    abs_path = os.path.abspath(workfile_path)
    path_bytes = abs_path.encode("utf-8")
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
    """Build absolute URL for a workspace endpoint."""
    base = f"{WORKSPACE_SERVER_URL}/workspace/{workspace_id}"
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


# -----------------------------------------------------------------------------
# Server discovery and lifecycle
# -----------------------------------------------------------------------------

def find_free_port(start: int = 5000, end: int = 5100) -> int:
    """Find the first available port in the given range."""
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No free port found in range {start}-{end}")


def find_running_server(host: str = "127.0.0.1", port_range: tuple = (5000, 5100), timeout: float = 1) -> tuple | None:
    """
    Scan port range for an active Workforce server via health check.
    
    Returns:
        (host, port) tuple if found, None if no server detected.
    """
    start_port, end_port = port_range
    for port in range(start_port, end_port + 1):
        try:
            url = f"http://{host}:{port}/workspaces"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    if "workspaces" in data:
                        return (host, port)
        except (urllib.error.URLError, urllib.error.HTTPError, ValueError, TimeoutError, OSError):
            continue
    return None


def resolve_server(host: str | None = None) -> str:
    """
    Find a running Workforce server or auto-start one.
    
    Args:
        host: Host to bind to (default: 127.0.0.1 for discovery, 0.0.0.0 for startup).
              If None, uses 127.0.0.1 for discovery, then 0.0.0.0 for startup.
    
    Returns:
        Full server URL (e.g., http://127.0.0.1:5042)
    
    Raises:
        RuntimeError: If server cannot be found or started.
    """
    discovery_host = host or "127.0.0.1"
    
    # Try to find existing server
    result = find_running_server(host=discovery_host)
    if result:
        found_host, found_port = result
        return f"http://{found_host}:{found_port}"
    
    # No server found, start one
    # Import here to avoid circular dependency
    from workforce.server import start_server
    
    startup_host = host or "0.0.0.0"
    try:
        start_server(background=True, host=startup_host)
    except Exception as e:
        raise RuntimeError(f"Failed to start server: {e}")
    
    # Try to find the newly started server
    # Use discovery host (127.0.0.1) since server on 0.0.0.0 is reachable locally via 127.0.0.1
    result = find_running_server(host=discovery_host, port_range=(5000, 5100), timeout=1)
    if result:
        found_host, found_port = result
        return f"http://{found_host}:{found_port}"
    
    raise RuntimeError("Server started but could not be discovered")
