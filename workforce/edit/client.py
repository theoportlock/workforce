import logging
import json
import urllib.request
from workforce.utils import _post

log = logging.getLogger(__name__)

def _get(base_url, endpoint):
    with urllib.request.urlopen(f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}") as response:
        return json.loads(response.read().decode("utf-8"))

def cmd_add_node(args, base_url, workspace_id):
    command = getattr(args, "command", None)
    payload = {
        "label": command if command is not None else args.label,
        "x": args.x,
        "y": args.y,
        "status": args.status,
        "command": command,
    }
    endpoint = f"/workspace/{workspace_id}/add-node"
    print(f"[CLIENT] POST {endpoint} {payload}")
    resp = _post(base_url, endpoint, payload)
    print(resp)

def cmd_remove_node(args, base_url, workspace_id):
    payload = {"node_id": args.node_id}
    endpoint = f"/workspace/{workspace_id}/remove-node"
    print(f"[CLIENT] POST {endpoint} {payload}")
    resp = _post(base_url, endpoint, payload)
    print(resp)

def cmd_add_edge(args, base_url, workspace_id):
    payload = {"source": args.source, "target": args.target, "edge_type": args.edge_type}
    endpoint = f"/workspace/{workspace_id}/add-edge"
    print(f"[CLIENT] POST {endpoint} {payload}")
    resp = _post(base_url, endpoint, payload)
    print(resp)


def cmd_edit_edge_type(args, base_url, workspace_id):
    payload = {"source": args.source, "target": args.target, "edge_type": args.edge_type}
    endpoint = f"/workspace/{workspace_id}/edit-edge-type"
    print(f"[CLIENT] POST {endpoint} {payload}")
    resp = _post(base_url, endpoint, payload)
    print(resp)

def cmd_remove_edge(args, base_url, workspace_id):
    payload = {"source": args.source, "target": args.target}
    endpoint = f"/workspace/{workspace_id}/remove-edge"
    print(f"[CLIENT] POST {endpoint} {payload}")
    resp = _post(base_url, endpoint, payload)
    print(resp)

def cmd_edit_status(args, base_url, workspace_id):
    payload = {
        "element_type": args.element_type,
        "element_id": args.element_id,
        "value": args.value,
    }
    endpoint = f"/workspace/{workspace_id}/edit-status"
    print(f"[CLIENT] POST {endpoint} {payload}")
    resp = _post(base_url, endpoint, payload)
    print(resp)

def cmd_edit_position(args, base_url, workspace_id):
    payload = {"node_id": args.node_id, "x": args.x, "y": args.y}
    endpoint = f"/workspace/{workspace_id}/edit-node-position"
    print(f"[CLIENT] POST {endpoint} {payload}")
    resp = _post(base_url, endpoint, payload)
    print(resp)

def cmd_edit_wrapper(args, base_url, workspace_id):
    payload = {"wrapper": args.wrapper}
    endpoint = f"/workspace/{workspace_id}/edit-wrapper"
    print(f"[CLIENT] POST {endpoint} {payload}")
    resp = _post(base_url, endpoint, payload)
    print(resp)

def cmd_edit_node_label(args, base_url, workspace_id):
    payload = {"node_id": args.node_id, "label": args.label}
    endpoint = f"/workspace/{workspace_id}/edit-node-label"
    print(f"[CLIENT] POST {endpoint} {payload}")
    resp = _post(base_url, endpoint, payload)
    print(resp)

def cmd_save_node_log(args, base_url, workspace_id):
    payload = {"node_id": args.node_id, "log": args.log}
    endpoint = f"/workspace/{workspace_id}/save-node-log"
    print(f"[CLIENT] POST {endpoint} {payload}")
    resp = _post(base_url, endpoint, payload)
    print(resp)

def cmd_edit_node_command(args, base_url, workspace_id):
    print(_post(base_url, f"/workspace/{workspace_id}/edit-node-command", {"node_id": args.node_id, "command": args.value}))

def cmd_list_nodes(args, base_url, workspace_id):
    print(json.dumps(_get(base_url, f"/workspace/{workspace_id}/list-nodes").get("nodes", []), indent=2))

def cmd_list_edges(args, base_url, workspace_id):
    print(json.dumps(_get(base_url, f"/workspace/{workspace_id}/list-edges").get("edges", []), indent=2))

def cmd_edit_edge_type_by_id(args, base_url, workspace_id):
    edges = _get(base_url, f"/workspace/{workspace_id}/list-edges").get("edges", [])
    edge = next((edge for edge in edges if str(edge.get("id")) == str(args.edge_id)), None)
    if edge is None:
        raise RuntimeError(f"Edge not found: {args.edge_id}")
    args.source, args.target = edge["source"], edge["target"]
    cmd_edit_edge_type(args, base_url, workspace_id)

def cmd_node_status(args, base_url, workspace_id):
    nodes = _get(base_url, f"/workspace/{workspace_id}/list-nodes").get("nodes", [])
    node = next((node for node in nodes if str(node.get("id")) == str(args.node_id)), None)
    if node is None:
        raise RuntimeError(f"Node not found: {args.node_id}")
    print(node.get("status", ""))
