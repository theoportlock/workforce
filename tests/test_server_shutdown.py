import time
from pathlib import Path

import requests

from workforce.server import start_server, stop_server
from workforce import utils


def _wait_for(predicate, timeout=8.0, interval=0.1):
    start = time.time()
    while time.time() - start < timeout:
        if predicate():
            return True
        time.sleep(interval)
    return False


def test_server_stops_after_client_disconnect(tmp_path):
    workfile = tmp_path / "Workfile"

    start_server(str(workfile), background=True)

    abs_path = str(workfile.resolve())
    registry = utils.clean_registry()
    assert abs_path in registry
    port = registry[abs_path]["port"]

    assert _wait_for(lambda: utils.is_port_in_use(port)), "Server did not start"

    base_url = f"http://127.0.0.1:{port}"

    # Register a client then disconnect; server should observe zero clients and stop.
    requests.post(base_url + "/client-connect", json={})
    requests.post(base_url + "/client-disconnect", json={})

    assert _wait_for(lambda: not utils.is_port_in_use(port)), "Server did not shut down after disconnect"

    # Ensure registry cleaned up
    stop_server(str(workfile))
