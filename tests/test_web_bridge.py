from workforce.web.bridge import PROTOCOL_VERSION, WebBridge, make_event_envelope


def test_get_graph_dispatches_get(monkeypatch):
    bridge = WebBridge(server_url="http://127.0.0.1:5042", workspace_id="ws_abc12345")
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
        "base_url": "http://127.0.0.1:5042/workspace/ws_abc12345",
        "endpoint": "/get-graph",
    }


def test_update_node_command_maps_command_to_label(monkeypatch):
    bridge = WebBridge(server_url="http://127.0.0.1:5042", workspace_id="ws_abc12345")
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
    assert called["base_url"] == "http://127.0.0.1:5042/workspace/ws_abc12345"
    assert called["endpoint"] == "/edit-node-label"
    assert called["payload"] == {"node_id": "n1", "label": "echo hi"}


def test_legacy_request_without_protocol_version_is_accepted(monkeypatch):
    bridge = WebBridge(server_url="http://127.0.0.1:5042", workspace_id="ws_abc12345")

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
    bridge = WebBridge(server_url="http://127.0.0.1:5042", workspace_id="ws_abc12345")

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
    bridge = WebBridge(server_url="http://127.0.0.1:5042", workspace_id="ws_old")

    def fake_post(base_url, endpoint, payload, retry_on_connect_error=False):
        assert base_url == "http://127.0.0.1:5042"
        assert endpoint == "/workspace/register"
        assert payload == {"path": "/tmp/new.wf"}
        return {"workspace_id": "ws_new", "url": "http://127.0.0.1:5042/workspace/ws_new"}

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


def test_make_event_envelope_shape():
    event = make_event_envelope("graph.updated", {"nodes": 3}, "ws_abc12345", 1234.5)

    assert event == {
        "event": "graph.updated",
        "payload": {"nodes": 3},
        "workspaceId": "ws_abc12345",
        "ts": 1234.5,
    }
