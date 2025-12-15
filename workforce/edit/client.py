import logging
from workforce.utils import _post

log = logging.getLogger(__name__)

def cmd_add_node(args, base_url):
    payload = {
        "label": args.label,
        "x": args.x,
        "y": args.y,
        "status": args.status,
    }
    print(f"[CLIENT] POST /add-node {payload}")
    resp = _post(base_url, "/add-node", payload)
    print(resp)

def cmd_remove_node(args, base_url):
    payload = {"node_id": args.node_id}
    print(f"[CLIENT] POST /remove-node {payload}")
    resp = _post(base_url, "/remove-node", payload)
    print(resp)

def cmd_add_edge(args, base_url):
    payload = {"source": args.source, "target": args.target}
    print(f"[CLIENT] POST /add-edge {payload}")
    resp = _post(base_url, "/add-edge", payload)
    print(resp)

def cmd_remove_edge(args, base_url):
    payload = {"source": args.source, "target": args.target}
    print(f"[CLIENT] POST /remove-edge {payload}")
    resp = _post(base_url, "/remove-edge", payload)
    print(resp)

def cmd_edit_status(args, base_url):
    payload = {
        "element_type": args.element_type,
        "element_id": args.element_id,
        "value": args.value,
    }
    print(f"[CLIENT] POST /edit-status {payload}")
    resp = _post(base_url, "/edit-status", payload)
    print(resp)

def cmd_edit_position(args, base_url):
    payload = {"node_id": args.node_id, "x": args.x, "y": args.y}
    print(f"[CLIENT] POST /edit-node-position {payload}")
    resp = _post(base_url, "/edit-node-position", payload)
    print(resp)

def cmd_edit_wrapper(args, base_url):
    payload = {"wrapper": args.wrapper}
    print(f"[CLIENT] POST /edit-wrapper {payload}")
    resp = _post(base_url, "/edit-wrapper", payload)
    print(resp)

def cmd_edit_node_label(args, base_url):
    payload = {"node_id": args.node_id, "label": args.label}
    print(f"[CLIENT] POST /edit-node-label {payload}")
    resp = _post(base_url, "/edit-node-label", payload)
    print(resp)

def cmd_save_node_log(args, base_url):
    payload = {"node_id": args.node_id, "log": args.log}
    print(f"[CLIENT] POST /save-node-log {payload}")
    resp = _post(base_url, "/save-node-log", payload)
    print(resp)
