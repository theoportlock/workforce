import os

from workforce.web.bridge import PROTOCOL_VERSION, WebBridge, make_event_envelope


def test_get_graph_dispatches_get(monkeypatch):
    bridge = WebBridge(server_url="http://127.0.0.1:5049", workspace_id="ws_abc12345")
    called = {}

    def fake_get(base_url, endpoint):
        called["base_url"] = base_url
        called["endpoint"] = endpoint
        return {"nodes": [], "links": []}

    monkeypatch.setattr("workforce.web.bridge._get_json", fake_get)

    response = bridge.handle_request(
        {
            "id": "r1",
            "method": "getGraph",
            "params": {},
            "protocolVersion": PROTOCOL_VERSION,
        }
    )

    assert response["ok"] is True
    assert response["result"] == {"nodes": [], "links": []}
    assert called == {
        "base_url": "http://127.0.0.1:5049/workspace/ws_abc12345",
        "endpoint": "/get-graph",
    }


def test_update_node_command_maps_command_to_label(monkeypatch):
    bridge = WebBridge(server_url="http://127.0.0.1:5049", workspace_id="ws_abc12345")
    called = {}

    def fake_post(base_url, endpoint, payload, retry_on_connect_error=False):
        called["base_url"] = base_url
        called["endpoint"] = endpoint
        called["payload"] = payload
        called["retry"] = retry_on_connect_error
        return {"status": "queued"}

    monkeypatch.setattr("workforce.web.bridge._post", fake_post)

    response = bridge.handle_request(
        {
            "id": "r2",
            "method": "updateNodeCommand",
            "params": {"node_id": "n1", "command": "echo hi"},
            "protocolVersion": PROTOCOL_VERSION,
        }
    )

    assert response["ok"] is True
    assert called["base_url"] == "http://127.0.0.1:5049/workspace/ws_abc12345"
    assert called["endpoint"] == "/edit-node-label"
    assert called["payload"] == {"node_id": "n1", "label": "echo hi"}


def test_update_status_dispatches_to_edit_status(monkeypatch):
    bridge = WebBridge(server_url="http://127.0.0.1:5049", workspace_id="ws_abc12345")
    called = {}

    def fake_post(base_url, endpoint, payload, retry_on_connect_error=False):
        called["base_url"] = base_url
        called["endpoint"] = endpoint
        called["payload"] = payload
        called["retry"] = retry_on_connect_error
        return {"status": "queued"}

    monkeypatch.setattr("workforce.web.bridge._post", fake_post)

    response = bridge.handle_request(
        {
            "id": "r-status",
            "method": "updateStatus",
            "params": {"kind": "node", "id": "n1", "status": "run"},
            "protocolVersion": PROTOCOL_VERSION,
        }
    )

    assert response["ok"] is True
    assert called["base_url"] == "http://127.0.0.1:5049/workspace/ws_abc12345"
    assert called["endpoint"] == "/edit-status"
    assert called["payload"] == {"element_type": "node", "element_id": "n1", "value": "run"}


def test_client_connect_requires_gui_socket_and_workfile(monkeypatch):
    bridge = WebBridge(server_url="http://127.0.0.1:5049", workspace_id="ws_abc12345")
    called = {}

    def fake_post(base_url, endpoint, payload, retry_on_connect_error=False):
        called["base_url"] = base_url
        called["endpoint"] = endpoint
        called["payload"] = payload
        return {"status": "connected", "client_id": "gui-1"}

    monkeypatch.setattr("workforce.web.bridge._post", fake_post)

    response = bridge.handle_request(
        {
            "id": "connect-1",
            "method": "clientConnect",
            "params": {
                "socketio_sid": "sid-123",
                "workfile_path": "/tmp/test.graphml",
                "client_type": "gui",
            },
            "protocolVersion": PROTOCOL_VERSION,
        }
    )

    assert response["ok"] is True
    assert called["endpoint"] == "/client-connect"
    assert called["payload"] == {
        "socketio_sid": "sid-123",
        "workfile_path": "/tmp/test.graphml",
        "client_type": "gui",
    }


def test_add_node_requires_only_label(monkeypatch):
    bridge = WebBridge(server_url="http://127.0.0.1:5049", workspace_id="ws_abc12345")
    called = {}

    def fake_post(base_url, endpoint, payload, retry_on_connect_error=False):
        called["endpoint"] = endpoint
        called["payload"] = payload
        return {"status": "queued"}

    monkeypatch.setattr("workforce.web.bridge._post", fake_post)

    response = bridge.handle_request(
        {
            "id": "add-min",
            "method": "addNode",
            "params": {"label": "hello"},
            "protocolVersion": PROTOCOL_VERSION,
        }
    )

    assert response["ok"] is True
    assert called["endpoint"] == "/add-node"
    assert called["payload"] == {"label": "hello"}


def test_client_disconnect_without_identifiers_is_allowed(monkeypatch):
    bridge = WebBridge(server_url="http://127.0.0.1:5049", workspace_id="ws_abc12345")
    called = {}

    def fake_post(base_url, endpoint, payload, retry_on_connect_error=False):
        called["endpoint"] = endpoint
        called["payload"] = payload
        return {"status": "disconnected"}

    monkeypatch.setattr("workforce.web.bridge._post", fake_post)

    response = bridge.handle_request(
        {
            "id": "disconnect-empty",
            "method": "clientDisconnect",
            "params": {},
            "protocolVersion": PROTOCOL_VERSION,
        }
    )

    assert response["ok"] is True
    assert called["endpoint"] == "/client-disconnect"
    assert called["payload"] == {"client_type": "gui", "client_id": None, "socketio_sid": None}


def test_client_disconnect_defaults_to_gui(monkeypatch):
    bridge = WebBridge(server_url="http://127.0.0.1:5049", workspace_id="ws_abc12345")
    called = {}

    def fake_post(base_url, endpoint, payload, retry_on_connect_error=False):
        called["endpoint"] = endpoint
        called["payload"] = payload
        return {"status": "disconnected"}

    monkeypatch.setattr("workforce.web.bridge._post", fake_post)

    response = bridge.handle_request(
        {
            "id": "disconnect-1",
            "method": "clientDisconnect",
            "params": {"client_id": "gui-1"},
            "protocolVersion": PROTOCOL_VERSION,
        }
    )

    assert response["ok"] is True
    assert called["endpoint"] == "/client-disconnect"
    assert called["payload"] == {
        "client_type": "gui",
        "client_id": "gui-1",
        "socketio_sid": None,
    }


def test_legacy_request_without_protocol_version_is_accepted(monkeypatch):
    bridge = WebBridge(server_url="http://127.0.0.1:5049", workspace_id="ws_abc12345")

    monkeypatch.setattr(
        "workforce.web.bridge._post",
        lambda base_url, endpoint, payload, retry_on_connect_error=False: {
            "status": "queued",
            "endpoint": endpoint,
        },
    )

    response = bridge.handle_request(
        {
            "id": "legacy",
            "method": "stopRuns",
            "params": {},
        }
    )

    assert response["ok"] is True
    assert response["result"]["endpoint"] == "/stop"


def test_unsupported_protocol_version_returns_error():
    bridge = WebBridge(server_url="http://127.0.0.1:5049", workspace_id="ws_abc12345")

    response = bridge.handle_request(
        {
            "id": "badver",
            "method": "getGraph",
            "params": {},
            "protocolVersion": "2.0",
        }
    )

    assert response["ok"] is False
    assert response["error"]["type"] == "BridgeProtocolError"
    assert "Unsupported protocolVersion" in response["error"]["message"]


def test_open_workflow_updates_workspace_id(monkeypatch):
    bridge = WebBridge(server_url="http://127.0.0.1:5049", workspace_id="ws_old")
    expected_path = os.path.abspath("/tmp/new.wf")

    def fake_post(base_url, endpoint, payload, retry_on_connect_error=False):
        assert base_url == "http://127.0.0.1:5049"
        assert endpoint == "/workspace/register"
        assert payload == {"path": expected_path}
        return {"workspace_id": "ws_new", "url": "http://127.0.0.1:5049/workspace/ws_new"}

    monkeypatch.setattr("workforce.web.bridge._post", fake_post)

    response = bridge.handle_request(
        {
            "id": "open1",
            "method": "openWorkflow",
            "params": {"path": "/tmp/new.wf"},
            "protocolVersion": PROTOCOL_VERSION,
        }
    )

    assert response["ok"] is True
    assert bridge.workspace_id == "ws_new"


def test_open_workflow_dialog_registers_workspace(monkeypatch):
    bridge = WebBridge(server_url="http://127.0.0.1:5049", workspace_id="ws_old")

    monkeypatch.setattr("workforce.web.bridge._choose_open_graphml_path", lambda current_path=None: "/tmp/open.graphml")

    def fake_post(base_url, endpoint, payload, retry_on_connect_error=False):
        assert base_url == "http://127.0.0.1:5049"
        assert endpoint == "/workspace/register"
        assert payload == {"path": os.path.abspath("/tmp/open.graphml")}
        return {"workspace_id": "ws_opened", "path": "/tmp/open.graphml"}

    monkeypatch.setattr("workforce.web.bridge._post", fake_post)

    response = bridge.handle_request(
        {
            "id": "open-dialog",
            "method": "openWorkflowDialog",
            "params": {},
            "protocolVersion": PROTOCOL_VERSION,
        }
    )

    assert response["ok"] is True
    assert response["result"]["cancelled"] is False
    assert bridge.workspace_id == "ws_opened"


def test_save_workflow_as_dialog_updates_workspace(monkeypatch):
    bridge = WebBridge(server_url="http://127.0.0.1:5049", workspace_id="ws_old")

    monkeypatch.setattr("workforce.web.bridge._choose_save_graphml_path", lambda current_path=None: "/tmp/saved.graphml")

    def fake_post(base_url, endpoint, payload, retry_on_connect_error=False):
        assert base_url == "http://127.0.0.1:5049/workspace/ws_old"
        assert endpoint == "/save-as"
        assert payload == {"new_path": "/tmp/saved.graphml"}
        return {
            "status": "saved",
            "new_path": "/tmp/saved.graphml",
            "new_workspace_id": "ws_saved",
            "new_base_url": "http://127.0.0.1:5049/workspace/ws_saved",
        }

    monkeypatch.setattr("workforce.web.bridge._post", fake_post)

    response = bridge.handle_request(
        {
            "id": "save-dialog",
            "method": "saveWorkflowAsDialog",
            "params": {},
            "protocolVersion": PROTOCOL_VERSION,
        }
    )

    assert response["ok"] is True
    assert response["result"]["cancelled"] is False
    assert bridge.workspace_id == "ws_saved"


def test_make_event_envelope_shape():
    event = make_event_envelope("graph.updated", {"nodes": 3}, "ws_abc12345", 1234.5)

    assert event == {
        "event": "graph.updated",
        "payload": {"nodes": 3},
        "workspaceId": "ws_abc12345",
        "ts": 1234.5,
    }


def test_get_runs_and_get_clients_dispatch_get(monkeypatch):
    bridge = WebBridge(server_url="http://127.0.0.1:5049", workspace_id="ws_abc12345")
    calls = []

    def fake_get(base_url, endpoint):
        calls.append((base_url, endpoint))
        return {"ok": True}

    monkeypatch.setattr("workforce.web.bridge._get_json", fake_get)

    runs_response = bridge.handle_request(
        {
            "id": "runs-1",
            "method": "getRuns",
            "params": {},
            "protocolVersion": PROTOCOL_VERSION,
        }
    )
    clients_response = bridge.handle_request(
        {
            "id": "clients-1",
            "method": "getClients",
            "params": {},
            "protocolVersion": PROTOCOL_VERSION,
        }
    )

    assert runs_response["ok"] is True
    assert clients_response["ok"] is True
    assert calls == [
        ("http://127.0.0.1:5049/workspace/ws_abc12345", "/runs"),
        ("http://127.0.0.1:5049/workspace/ws_abc12345", "/clients"),
    ]


def test_update_status_validation_error_message():
    bridge = WebBridge(server_url="http://127.0.0.1:5049", workspace_id="ws_abc12345")

    response = bridge.handle_request(
        {
            "id": "bad-status",
            "method": "updateStatus",
            "params": {"id": "n1", "status": "run"},
            "protocolVersion": PROTOCOL_VERSION,
        }
    )

    assert response["ok"] is False
    assert response["error"]["type"] == "BridgeProtocolError"
    assert (
        response["error"]["message"]
        == "updateStatus requires element_type/kind, element_id/id, and value/status"
    )
