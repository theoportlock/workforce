#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import socketio
import json

sio = socketio.Client()

@sio.event
def connect():
    print("Connected to Workforce server")

@sio.event
def disconnect():
    print("Disconnected from server")

@sio.on("graph_data")
def on_graph_data(data):
    print("Received full graph:")
    print(json.dumps(data, indent=2))

@sio.on("graph_updated")
def on_graph_updated(data):
    print("Graph update:", data)

@sio.on("save_complete")
def on_save_complete(data):
    print("Save complete:", data)

# Connect to the server
sio.connect("http://localhost:5000")

# Example interaction
sio.emit("add_node", {"id": "n1", "label": "Example Node", "x": 50, "y": 75})
sio.emit("add_edge", {"source": "n1", "target": "n2"})

# Save graph
sio.emit("save_graph")

