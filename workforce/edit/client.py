import logging
from workforce.utils import _post

log = logging.getLogger(__name__)

def cmd_add_node(args, base_url, workspace_id):
    payload = {
        "label": args.label,
        "x": args.x,
        "y": args.y,
        "status": args.status,
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
    payload = {"source": args.source, "target": args.target}
    endpoint = f"/workspace/{workspace_id}/add-edge"
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
