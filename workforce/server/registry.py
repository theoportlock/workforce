# workforce/server/registry.py
import os
import platform
import signal
import subprocess
import sys
from typing import Dict

from workforce.utils import clean_registry, save_registry, load_registry, find_free_port


def list_servers():
    registry = clean_registry()
    if not registry:
        print("No active Workforce servers.")
        return

    print("Active Workforce servers:")
    for path, info in registry.items():
        print(f" - {path}")
        print(f"   http://127.0.0.1:{info['port']} (PID {info['pid']}) clients={info.get('clients',0)}")


def stop_server(filename: str | None):
    if not filename:
        print("No file specified.")
        return

    abs_path = os.path.abspath(filename)
    registry = clean_registry()

    if abs_path not in registry:
        print(f"No active server for '{filename}'")
        return

    entry = registry.pop(abs_path)
    save_registry(registry)

    pid = entry.get("pid")
    port = entry.get("port")

    try:
        if platform.system() == "Windows":
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], check=False)
        else:
            os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        print("Process already stopped")

    print(f"Stopped server for '{filename}' (PID {pid}) port {port}")


def start_server(filename: str, port: int | None = None, background: bool = True):
    if not filename:
        sys.exit("No file specified")

    abs_path = os.path.abspath(filename)
    registry = clean_registry()

    if abs_path in registry:
        print(f"Server already running: http://127.0.0.1:{registry[abs_path]['port']}")
        return

    if port is None:
        port = find_free_port()

    if background:
        cmd = [
            sys.executable,
            "-m",
            "workforce.server.app",
            abs_path,
            "--port",
            str(port),
            "--foreground"
        ]
        process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        registry[abs_path] = {"port": port, "pid": process.pid, "clients": 0}
        save_registry(registry)
        print(f"Server started for '{abs_path}' on port {port}")
        return

    # If foreground run is desired, import app runner and call it
    from workforce.server.app import run_server_foreground
    registry[abs_path] = {"port": port, "pid": os.getpid(), "clients": 0}
    save_registry(registry)
    try:
        run_server_foreground(abs_path, port)
    finally:
        reg = clean_registry()
        reg.pop(abs_path, None)
        save_registry(reg)
        print("Clean shutdown; registry updated")

