# workforce/server/app.py
import argparse
import os
import time
import threading

from flask import Flask, request, jsonify
from flask_socketio import SocketIO

from .graph_store import GraphStore
from .graph_queue import GraphWorker
from .tasks import run_pipeline_async, run_node_async
from .registry import clean_registry, save_registry, load_registry


def create_app(abs_path: str, port: int = 5000):
    app = Flask(__name__)
    socketio = SocketIO(app, cors_allowed_origins="*")

    store = GraphStore(abs_path)
    worker = GraphWorker(store, socketio, room=abs_path)
    worker.start()

    client_count = {"count": 0}

    def update_registry_clients():
        reg = load_registry()
        reg[abs_path]["clients"] = client_count["count"]
        save_registry(reg)

    @app.route("/client-connect", methods=["POST"])
    def client_connect():
        client_count["count"] += 1
        update_registry_clients()
        return jsonify({"clients": client_count["count"]})

    @app.route("/client-disconnect", methods=["POST"])
    def client_disconnect():
        client_count["count"] = max(0, client_count["count"] - 1)
        update_registry_clients()
        if client_count["count"] == 0:
        # graceful auto-shutdown after brief delay
            threading.Thread(target=lambda: (time.sleep(5), os.kill(os.getpid(), 2)), daemon=True).start()
        return jsonify({"clients": client_count["count"]})

    @app.route("/get-graph", methods=["GET"])
    def get_graph():
        return jsonify(store.node_link_data())

    @app.route("/add-node", methods=["POST"])
    def add_node():
        data = request.get_json(force=True)
        worker.enqueue("add_node", label=data["label"], x=data.get("x", 0), y=data.get("y", 0), status=data.get("status", ""))
        return jsonify({"status": "queued"}), 202

    @app.route("/remove-node", methods=["POST"])
    def remove_node():
        data = request.get_json(force=True)
        worker.enqueue("remove_node", node_id=data["node_id"])
        return jsonify({"status": "queued"}), 202

    @app.route("/add-edge", methods=["POST"])
    def add_edge():
        data = request.get_json(force=True)
        worker.enqueue("add_edge", source=data["source"], target=data["target"])
        return jsonify({"status": "queued"}), 202

    @app.route("/remove-edge", methods=["POST"])
    def remove_edge():
        data = request.get_json(force=True)
        worker.enqueue("remove_edge", source=data["source"], target=data["target"])
        return jsonify({"status": "queued"}), 202

    @app.route("/edit-status", methods=["POST"])
    def edit_status():
        data = request.get_json(force=True)
        worker.enqueue("edit_status", element_type=data["element_type"], element_id=data["element_id"], value=data.get("value", ""))
        return jsonify({"status": "queued"}), 202

    @app.route("/update-node", methods=["POST"])
    def update_node():
        data = request.get_json(force=True)
        worker.enqueue("update_node", data=data)
        return jsonify({"status": "queued"}), 202

    @app.route("/run", methods=["POST"])
    def run_pipeline():
        data = request.get_json(force=True) if request.data else {}
        prefix = data.get("prefix", "")
        suffix = data.get("suffix", "")
        run_pipeline_async(f"http://127.0.0.1:{port}/get-graph", prefix, suffix)
        return jsonify({"status": "started"}), 202

    @app.route("/run-node", methods=["POST"])
    def run_node_endpoint():
        data = request.get_json(force=True)
        node = data["node"]
        prefix = data.get("prefix", "")
        suffix = data.get("suffix", "")
        run_node_async(f"http://127.0.0.1:{port}/get-graph", node, prefix, suffix)
        return jsonify({"status": "started"}), 202

    # expose objects for importers
    app._graph_store = store
    app._graph_worker = worker
    app._socketio = socketio


    return app, socketio
