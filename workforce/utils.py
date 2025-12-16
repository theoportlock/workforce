#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
utils.py — Shared Workforce utilities for registry management, networking,
and resolving filenames/URLs into active server instances.
"""

from contextlib import closing
import json
import os
import socket
import sys
import tempfile
import urllib.error
import urllib.request
import subprocess
import time
import requests  # Add requests import

REGISTRY_PATH = os.path.join(tempfile.gettempdir(), "workforce_servers.json")

# -----------------------------------------------------------------------------
# HTTP POST helper
# -----------------------------------------------------------------------------

def _post(base_url: str, endpoint: str, payload: dict | None = None) -> dict:
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

    except urllib.error.URLError as e:
        raise RuntimeError(f"Failed to POST to {url}: {e}")

    except Exception as e:
        raise RuntimeError(f"Unexpected error POSTing to {url}: {e}")

def shell_quote_multiline(script: str) -> str:
    return script.replace("'", "'\\''")

# -----------------------------------------------------------------------------
# Registry utilities
# -----------------------------------------------------------------------------

def load_registry() -> dict:
    if os.path.exists(REGISTRY_PATH):
        try:
            with open(REGISTRY_PATH, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_registry(registry: dict):
    with open(REGISTRY_PATH, "w") as f:
        json.dump(registry, f, indent=2)


def is_port_in_use(port: int) -> bool:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def clean_registry() -> dict:
    """Remove entries for inactive servers."""
    registry = load_registry()
    updated = {}

    for path, info in registry.items():
        port = info.get("port")
        if port and is_port_in_use(port):
            updated[path] = info

    if updated != registry:
        save_registry(updated)

    return updated


def find_free_port(start: int = 5000, end: int = 6000) -> int:
    for port in range(start, end):
        if not is_port_in_use(port):
            return port
    raise RuntimeError("No free ports available in range 5000–6000.")


def default_workfile() -> str | None:
    path = os.path.join(os.getcwd(), "Workfile")
    return path if os.path.exists(path) else None

# -----------------------------------------------------------------------------
# URL / FILE RESOLUTION LOGIC
# -----------------------------------------------------------------------------

def is_url(s: str) -> bool:
    return s.startswith("http://") or s.startswith("https://")


def launch_server_for_file(filename: str) -> str:
    """
    Launch a workforce server for a given filename.
    Returns a URL to connect to.
    """
    filename = os.path.abspath(filename)
    port = find_free_port()

    cmd = [
        sys.executable,
        "-m", "workforce",
        "server", "start",
        filename,
        "--port", str(port)
    ]
    
    # Use Popen with a list of args to avoid shell=True for better security and cross-platform behavior.
    process = subprocess.Popen(cmd)

    # Persist to registry
    registry = load_registry()
    registry[filename] = {"port": port, "pid": process.pid}
    save_registry(registry)

    # Wait for the server to become responsive
    for _ in range(10):  # Try for up to 2 seconds
        if is_port_in_use(port):
            break
        time.sleep(0.2)

    return f"http://127.0.0.1:{port}"


def resolve_target(path_or_url):
    if is_url(path_or_url):
        return path_or_url

    abs_path = os.path.abspath(path_or_url)
    registry = clean_registry()

    if abs_path in registry:
        info = registry[abs_path]
        return f"http://127.0.0.1:{info['port']}"

    # Start server in background
    from workforce.server import start_server
    start_server(path_or_url, background=True)

    # Check registry again
    registry = clean_registry()
    if abs_path in registry:
        info = registry[abs_path]
        return f"http://127.0.0.1:{info['port']}"

    raise RuntimeError(f"Failed to start server for {path_or_url}")


def resolve_port(filename: str | None = None) -> tuple[str, int]:
    registry = clean_registry()
    if not registry:
        raise RuntimeError("No active servers running.")

    if filename:
        abs_path = os.path.abspath(filename)
        if abs_path not in registry:
            raise RuntimeError(f"No server found for '{filename}'")
        return abs_path, registry[abs_path]["port"]

    # Autoselect if only one server is running
    if len(registry) == 1:
        path, info = next(iter(registry.items()))
        return path, info["port"]

    raise RuntimeError("Multiple servers active — specify filename.")
