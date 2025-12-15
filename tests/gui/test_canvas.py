import pytest
from unittest.mock import MagicMock
from workforce.gui.canvas import Canvas

def test_add_node_to_canvas():
    canvas = Canvas(MagicMock())  # pass fake master
    node_id = canvas.add_node("Test Node", x=10, y=20)
    assert node_id in canvas.nodes
