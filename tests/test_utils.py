import pytest
from unittest.mock import patch
from workforce import utils

def test_shell_quote_multiline():
    cmd = "echo 'hello\nworld'"
    quoted = utils.shell_quote_multiline(cmd)
    assert "\n" not in quoted
    assert "'" in quoted

@patch("workforce.utils.requests.post")
def test_post(mock_post):
    mock_post.return_value.json.return_value = {"status": "ok"}
    resp = utils._post("http://example.com", "/endpoint", {"a": 1})
    assert resp["status"] == "ok"
