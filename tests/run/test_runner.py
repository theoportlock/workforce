import pytest
from unittest.mock import patch, MagicMock
from workforce.run.client import Runner

@patch("workforce.run.client.subprocess.Popen")
def test_execute_node(mock_popen):
    process_mock = MagicMock()
    process_mock.communicate.return_value = ("stdout", "stderr")
    process_mock.returncode = 0
    mock_popen.return_value = process_mock

    runner = Runner("http://fake-server")
    runner.set_node_status = MagicMock()
    runner.send_node_log = MagicMock()

    runner.execute_node("node1", "echo test")
    runner.set_node_status.assert_any_call("node1", "running")
    runner.set_node_status.assert_any_call("node1", "ran")
