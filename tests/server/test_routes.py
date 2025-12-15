import json
import pytest
from unittest.mock import patch
from workforce.server import routes

@pytest.fixture
def client():
    assert hasattr(routes, "app"), "routes.app test Flask app missing"
    return routes.app.test_client()

@patch("workforce.edit.client.cmd_add_node", autospec=True)
def test_add_node_route(mock_add_node, client):
    resp = client.post(
        "/add-node",
        data=json.dumps({"label": "Test"}),
        content_type="application/json"
    )
    # API enqueues the change and returns 202
    assert resp.status_code == 202
