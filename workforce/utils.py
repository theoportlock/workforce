#!/usr/bin/env python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
utils.py — Shared Workforce utilities for registry management and networking.
"""

import json
import sys
import os
import socket
import tempfile
import requests
from contextlib import closing

REGISTRY_PATH = os.path.join(tempfile.gettempdir(), "workforce_servers.json")

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
    from workforce.utils import is_port_in_use  # avoid circular imports
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


def resolve_port(filename: str | None = None) -> tuple[str, int]:
    """Find port from registry for given file (or default Workfile)."""
    registry = load_registry()
    if not registry:
        print("No active servers running.", file=sys.stderr)
        sys.exit(1)

    if filename:
        abs_path = os.path.abspath(filename)
        if abs_path not in registry:
            print(f"No server found for '{filename}'", file=sys.stderr)
            sys.exit(1)
        port = registry[abs_path]["port"]
        return abs_path, port

    # If only one server is active, use it automatically
    if len(registry) == 1:
        path, info = next(iter(registry.items()))
        return path, info["port"]

    print("Multiple servers active. Specify file path explicitly.", file=sys.stderr)
    sys.exit(1)

