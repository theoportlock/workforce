from workforce.web.bridge import PROTOCOL_VERSION, WebBridge


def test_bridge_method_dispatch_to_http_endpoints(monkeypatch):
    bridge = WebBridge(server_url="http://127.0.0.1:5042", workspace_id="ws_abc12345")
    calls = []

    def fake_post(base_url, endpoint, payload, retry_on_connect_error=False):
        calls.append(("POST", base_url, endpoint, payload, retry_on_connect_error))
        return {"endpoint": endpoint}

    def fake_get(base_url, endpoint):
        calls.append(("GET", base_url, endpoint))
        return {"endpoint": endpoint}

    monkeypatch.setattr("workforce.web.bridge._post", fake_post)
    monkeypatch.setattr("workforce.web.bridge._get_json", fake_get)

    r1 = bridge.handle_request({"id": "1", "method": "getGraph", "params": {}, "protocolVersion": PROTOCOL_VERSION})
    r2 = bridge.handle_request({"id": "2", "method": "addEdge", "params": {"source": "a", "target": "b"}, "protocolVersion": PROTOCOL_VERSION})

    assert r1["ok"] is True
    assert r2["ok"] is True
    assert calls[0] == ("GET", "http://127.0.0.1:5042/workspace/ws_abc12345", "/get-graph")
    assert calls[1][0:3] == ("POST", "http://127.0.0.1:5042/workspace/ws_abc12345", "/add-edge")


def test_bridge_envelope_validation_and_error_shape():
    bridge = WebBridge(server_url="http://127.0.0.1:5042", workspace_id="ws_abc12345")

    missing_method = bridge.handle_request({"id": "bad-1", "params": {}, "protocolVersion": PROTOCOL_VERSION})
    assert missing_method == {
        "id": "bad-1",
        "ok": False,
        "error": {"type": "BridgeProtocolError", "message": "method is required"},
    }

    bad_params = bridge.handle_request({"id": "bad-2", "method": "getGraph", "params": ["x"], "protocolVersion": PROTOCOL_VERSION})
    assert bad_params["ok"] is False
    assert bad_params["error"]["type"] == "BridgeProtocolError"
    assert bad_params["error"]["message"] == "params must be an object"

    unsupported = bridge.handle_request({"id": "bad-3", "method": "nope", "params": {}, "protocolVersion": PROTOCOL_VERSION})
    assert unsupported["ok"] is False
    assert unsupported["error"]["type"] == "BridgeProtocolError"
    assert "unsupported method: nope" in unsupported["error"]["message"]


def test_bridge_returns_uniform_error_shape_for_handler_exceptions(monkeypatch):
    bridge = WebBridge(server_url="http://127.0.0.1:5042", workspace_id="ws_abc12345")

    monkeypatch.setattr(
        "workforce.web.bridge._post",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    response = bridge.handle_request(
        {
            "id": "err-1",
            "method": "runWorkflow",
            "params": {},
            "protocolVersion": PROTOCOL_VERSION,
        }
    )

    assert response == {
        "id": "err-1",
        "ok": False,
        "error": {"type": "RuntimeError", "message": "boom"},
    }
