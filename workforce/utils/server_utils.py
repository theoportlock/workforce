# workforce/utils/server_utils.py

import os
import subprocess
import time
import socketio
from workforce.server import load_registry, save_registry, find_free_port

def ensure_server_running(filename):
    """Ensure a Workforce server is running for the given GraphML file."""
    filename = os.path.abspath(filename)
    registry = load_registry()

    if filename in registry:
        port = registry[filename]
        print(f"✓ Found existing server for {filename} on port {port}")
    else:
        print(f"⚙️  No server found for {filename}, starting one...")
        port = find_free_port()
        subprocess.Popen(
            ["python3", "-m", "workforce.serve", "start", filename, "--port", str(port)], # Use sys executable here
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # Give the server a moment to start
        time.sleep(1.5)
        registry[filename] = port
        save_registry(registry)
        print(f"🚀 Started server for {filename} on port {port}")

    return "127.0.0.1", port


def get_client(filename):
    """Return a connected Socket.IO client for the given file."""
    host, port = ensure_server_running(filename)
    sio = socketio.Client()
    sio.connect(f"http://{host}:{port}")
    return sio

