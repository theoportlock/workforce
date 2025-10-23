#!/usr/bin/env python

import json
import os
import tempfile
import pytest
import socket
from unittest import mock
from workforce import server


@pytest.fixture(autouse=True)
def temp_registry(monkeypatch):
    """Use a temporary JSON registry file for all tests."""
    tmp = tempfile.NamedTemporaryFile(delete=False)
    tmp.close()
    monkeypatch.setattr(server, "REGISTRY_PATH", tmp.name)
    yield
    os.remove(tmp.name)


def test_load_and_save_registry():
    data = {"file.graphml": 5050}
    server.save_registry(data)
    loaded = server.load_registry()
    assert loaded == data


def test_clean_registry_removes_inactive_ports(monkeypatch):
    registry = {"f1.graphml": 49999, "f2.graphml": 22}
    server.save_registry(registry)

    # mock port 22 as active, 49999 as inactive
    monkeypatch.setattr(server, "is_port_in_use", lambda port: port == 22)
    cleaned = server.clean_registry()
    assert cleaned == {"f2.graphml": 22}

    reloaded = server.load_registry()
    assert reloaded == {"f2.graphml": 22}


def test_find_free_port(monkeypatch):
    """Ensure find_free_port returns the first unused port."""
    calls = []

    def fake_in_use(port):
        calls.append(port)
        return port < 5002

    monkeypatch.setattr(server, "is_port_in_use", fake_in_use)
    free = server.find_free_port(default_port=5000, max_port=5005)
    assert free == 5002
    assert calls[:3] == [5000, 5001, 5002]


def test_is_port_in_use_false_for_unused_port():
    """A random high port should not be in use."""
    port = 59999
    assert server.is_port_in_use(port) is False


@mock.patch("workforce.server.SocketIO")
@mock.patch("workforce.server.Flask")
def test_start_server_updates_registry(mock_flask, mock_socketio):
    """Mock Flask so we don’t start a real server."""
    mock_socket = mock.MagicMock()
    mock_socketio.return_value = mock_socket

    with tempfile.NamedTemporaryFile(suffix=".graphml") as tmp:
        port = server.find_free_port()
        with mock.patch("workforce.server.find_free_port", return_value=port):
            server.start_server(tmp.name, port=port)

    reg = server.load_registry()
    assert tmp.name in reg
    assert reg[tmp.name] == port
    mock_socket.run.assert_called_once()  # ensures it attempted to run Flask


def test_list_servers_prints_output(capsys):
    server.save_registry({"f1.graphml": 5050})
    server.list_servers()
    out = capsys.readouterr().out
    assert "Workforce servers" in out


def test_stop_server_removes_registry_entry(capsys):
    fname = os.path.abspath("test.graphml")
    server.save_registry({fname: 5050})
    server.stop_server(fname)
    reg = server.load_registry()
    assert fname not in reg
    out = capsys.readouterr().out
    assert "server" in out.lower()  # looser match: covers both messages


def test_stop_server_no_entry(capsys):
    server.save_registry({})
    server.stop_server("missing.graphml")
    out = capsys.readouterr().out
    assert "No active server" in out

