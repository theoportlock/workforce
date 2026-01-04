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

# Workspace server configuration
WORKSPACE_SERVER_URL = "http://localhost:5000"
WORKSPACE_SERVER_PORT = 5000

# -----------------------------------------------------------------------------
# Workspace identification
# -----------------------------------------------------------------------------

def compute_workspace_id(workfile_path: str) -> str:
    """Compute deterministic workspace ID from absolute Workfile path."""
    abs_path = os.path.abspath(workfile_path)
    path_bytes = abs_path.encode("utf-8")
    hash_hex = hashlib.sha256(path_bytes).hexdigest()[:8]
    return f"ws_{hash_hex}"


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
