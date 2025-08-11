# flask_server.py
from flask import Flask, request, jsonify
import networkx as nx
import subprocess
from utils_fileio import GraphMLAtomic  # renamed utils to utils_fileio for local lock I/O

FILENAME = "pipeline.graphml"

app = Flask(__name__)

@app.route("/graph", methods=["GET"])
def get_graph():
    with GraphMLAtomic(FILENAME) as ga:
        return jsonify(nx.node_link_data(ga.G))

@app.route("/update-status", methods=["POST"])
def update_status():
    data = request.json
    element_type = data["type"]
    element_id = data["id"]
    status = data["status"]

    with GraphMLAtomic(FILENAME) as ga:
        if element_type == "node":
            ga.G.nodes[element_id]["status"] = status
        elif element_type == "edge":
            ga.G.edges[element_id]["status"] = status
        else:
            return {"error": "Invalid type"}, 400
        ga.mark_modified()
    return {"status": "ok"}

@app.route("/run-command", methods=["POST"])
def run_command():
    data = request.json
    node_id = data["id"]
    command = data["command"]
    try:
        subprocess.run(command, shell=True, check=True)
        update_status_node(node_id, "ran")
    except subprocess.CalledProcessError:
        update_status_node(node_id, "fail")
    return {"status": "ok"}

def update_status_node(node_id, status):
    with GraphMLAtomic(FILENAME) as ga:
        ga.G.nodes[node_id]["status"] = status
        ga.mark_modified()

if __name__ == "__main__":
    app.run(port=5000)
