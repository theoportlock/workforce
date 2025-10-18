#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
parse.py — Utilities for Workforce GraphML and server handling
"""

import os
import sys
import socket
import tempfile
import hashlib
import networkx as nx
from contextlib import closing


# ---------------------------------------------------------------------
# GraphML utilities
# ---------------------------------------------------------------------

class GraphMLAtomic:
    """Atomic read/write context manager for GraphML files."""

    def __init__(self, filename):
        self.filename = filename
        self.modified = False

    def __enter__(self):
        if not os.path.exists(self.filename):
            nx.write_graphml(nx.DiGraph(), self.filename)
        self.G = nx.read_graphml(self.filename)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.modified:
            nx.write_graphml(self.G, self.filename)

    def mark_modified(self):
        self.modified = True


# ---------------------------------------------------------------------
# Lock + file hashing utilities
# ---------------------------------------------------------------------

def file_hash(path: str) -> str:
    """Return a short hash for a given file path."""
    return hashlib.sha256(path.encode("utf-8")).hexdigest()[:16]


def get_lockfile(filename: str) -> str:
    """Return the temporary lockfile path for a given GraphML file."""
    return os.path.join(tempfile.gettempdir(), f"workforce_server_{file_hash(filename)}.lock")


def acquire_lock_or_exit(lockfile: str, filename: str):
    """Prevent multiple servers running for the same GraphML file."""
    if os.path.exists(lockfile):
        print(f"Server for '{filename}' already running (lockfile exists). Exiting.")
        sys.exit(0)
    with open(lockfile, "w") as f:
        f.write("locked")


def release_lock(lockfile: str):
    """Remove the server lockfile on exit."""
    if os.path.exists(lockfile):
        os.remove(lockfile)


# ---------------------------------------------------------------------
# Port management + server launcher
# ---------------------------------------------------------------------

def find_free_port(default_port=5000, max_port=6000):
    """Find the first available TCP port starting from default_port."""
    for port in range(default_port, max_port):
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
            if s.connect_ex(('127.0.0.1', port)) != 0:
                return port
    raise RuntimeError("No free port found in range.")


def start_server(socketio, app, filename, default_port=5000):
    """
    Start the Flask-SocketIO server on an available port.
    Keeps running until stopped with Ctrl+C.
    """
    port = find_free_port(default_port)
    print(f"Serving '{filename}' on http://127.0.0.1:{port}")
    print("Press CTRL+C to stop the server.")
    socketio.run(app, host="127.0.0.1", port=port)


# ---------------------------------------------------------------------
# Main (optional test entry point)
# ---------------------------------------------------------------------

if __name__ == "__main__":
    # Simple test for port allocation
    print(f"Found free port: {find_free_port()}")

