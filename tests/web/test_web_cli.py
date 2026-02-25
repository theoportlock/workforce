import sys

import pytest

from workforce import __main__ as wf_main


def test_wf_web_registers_workspace_and_opens_browser(monkeypatch, capsys):
    opened = []
    calls = {}

    monkeypatch.setattr(wf_main, "ensure_workfile", lambda path=None: "/tmp/demo.graphml")

    def fake_resolve_server(server_url=None):
        calls["server_url_arg"] = server_url
        return "http://127.0.0.1:6500"

    monkeypatch.setattr(wf_main.utils, "resolve_server", fake_resolve_server)

    def fake_register_workspace(server_url, workfile_path):
        calls["register"] = (server_url, workfile_path)
        return {
            "workspace_id": "ws_test1234",
            "url": "http://127.0.0.1:6500/workspace/ws_test1234",
        }

    monkeypatch.setattr(wf_main, "register_workspace", fake_register_workspace)
    monkeypatch.setattr(wf_main.webbrowser, "open", lambda url: opened.append(url) or True)
    monkeypatch.setattr(sys, "argv", ["wf", "web", "/tmp/demo.graphml", "--server-url", "http://x:1"])

    wf_main._main_impl()

    assert calls["server_url_arg"] == "http://x:1"
    assert calls["register"] == ("http://127.0.0.1:6500", "/tmp/demo.graphml")
    assert opened == ["http://127.0.0.1:6500/workspace/ws_test1234"]

    out = capsys.readouterr().out
    assert "Opened workspace ws_test1234 in browser" in out
    assert "workfile: /tmp/demo.graphml" in out


def test_wf_web_accepts_workspace_url_without_register(monkeypatch):
    opened = []

    monkeypatch.setattr(wf_main, "register_workspace", lambda *_args, **_kwargs: pytest.fail("register_workspace should not be called"))
    monkeypatch.setattr(wf_main.webbrowser, "open", lambda url: opened.append(url) or True)
    monkeypatch.setattr(
        sys,
        "argv",
        ["wf", "web", "http://example.com:5049/workspace/ws_abc12345"],
    )

    wf_main._main_impl()

    assert opened == ["http://example.com:5049/workspace/ws_abc12345"]


def test_wf_web_invalid_workspace_url_exits(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["wf", "web", "http://example.com:5049/workspace/not_a_workspace"])

    with pytest.raises(SystemExit) as exc:
        wf_main._main_impl()

    assert exc.value.code == 1
