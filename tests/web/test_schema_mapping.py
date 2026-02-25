import networkx as nx

from workforce.edit import graph as edit_graph


def test_json_graphml_roundtrip_preserves_command_prefix_suffix_and_status(temp_graph_file):
    graph = nx.DiGraph()
    graph.graph["wrapper"] = "python -c '{}'"

    graph.add_node(
        "n1",
        label="echo hello",
        command="echo hello",
        prefix="set -e",
        suffix="echo done",
        status="running",
        x="10",
        y="20",
    )
    graph.add_node("n2", label="echo bye", status="ran", x="30", y="40")
    graph.add_edge("n1", "n2", id="e1", edge_type="non-blocking", status="fail")

    payload = nx.node_link_data(graph, edges="links")
    restored_graph = nx.node_link_graph(payload, edges="links")
    edit_graph.save_graph(restored_graph, temp_graph_file)

    loaded = edit_graph.load_graph(temp_graph_file)

    assert loaded.nodes["n1"]["command"] == "echo hello"
    assert loaded.nodes["n1"]["prefix"] == "set -e"
    assert loaded.nodes["n1"]["suffix"] == "echo done"
    assert loaded.nodes["n1"]["status"] == "running"
    assert loaded.nodes["n2"]["status"] == "ran"
    assert loaded["n1"]["n2"]["edge_type"] == "non-blocking"
    assert loaded["n1"]["n2"]["status"] == "fail"


def test_edge_type_normalization_and_status_persistence(temp_graph_file):
    graph = nx.DiGraph()
    graph.add_node("a", label="A")
    graph.add_node("b", label="B")
    edit_graph.save_graph(graph, temp_graph_file)

    result = edit_graph.add_edge_to_graph(temp_graph_file, "a", "b", edge_type="non_blocking")
    edge_id = result["edge_id"]

    status_result = edit_graph.edit_status_in_graph(temp_graph_file, "edge", edge_id, "ran")

    loaded = edit_graph.load_graph(temp_graph_file)

    assert status_result == {"status": "updated"}
    assert loaded["a"]["b"]["edge_type"] == "non-blocking"
    assert loaded["a"]["b"]["status"] == "ran"
