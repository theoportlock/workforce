import argparse
from .client import (
    cmd_add_node, cmd_remove_node, cmd_add_edge, cmd_remove_edge,
    cmd_edit_status, cmd_edit_position, cmd_edit_wrapper,
    cmd_edit_node_label, cmd_save_node_log
)
from workforce.utils import compute_workspace_id, get_absolute_path, default_workfile

def main():
    parser = argparse.ArgumentParser(prog="wf-edit", description="Workforce edit CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    en = sub.add_parser("add-node")
    en.add_argument("base_url")
    en.add_argument("label")
    en.add_argument("--x", type=float, default=0)
    en.add_argument("--y", type=float, default=0)
    en.add_argument("--status", default="")
    en.set_defaults(func=cmd_add_node)

    ern = sub.add_parser("remove-node")
    ern.add_argument("base_url")
    ern.add_argument("node_id")
    ern.set_defaults(func=cmd_remove_node)

    ee = sub.add_parser("add-edge")
    ee.add_argument("base_url")
    ee.add_argument("source")
    ee.add_argument("target")
    ee.set_defaults(func=cmd_add_edge)

    ere = sub.add_parser("remove-edge")
    ere.add_argument("base_url")
    ere.add_argument("source")
    ere.add_argument("target")
    ere.set_defaults(func=cmd_remove_edge)

    es = sub.add_parser("edit-status")
    es.add_argument("base_url")
    es.add_argument("element_type", choices=["node", "edge"])
    es.add_argument("element_id")
    es.add_argument("value")
    es.set_defaults(func=cmd_edit_status)

    ep = sub.add_parser("edit-position")
    ep.add_argument("base_url")
    ep.add_argument("node_id")
    ep.add_argument("x", type=float)
    ep.add_argument("y", type=float)
    ep.set_defaults(func=cmd_edit_position)

    ew = sub.add_parser("edit-wrapper")
    ew.add_argument("base_url")
    ew.add_argument("wrapper")
    ew.set_defaults(func=cmd_edit_wrapper)

    enl = sub.add_parser("edit-node-label")
    enl.add_argument("base_url")
    enl.add_argument("node_id")
    enl.add_argument("label")
    enl.set_defaults(func=cmd_edit_node_label)

    sn = sub.add_parser("save-node-log")
    sn.add_argument("base_url")
    sn.add_argument("node_id")
    sn.add_argument("log")
    sn.set_defaults(func=cmd_save_node_log)

    args = parser.parse_args()
    # base_url passed as first arg in each subcommand; call the mapped function
    kwargs = vars(args)
    func = kwargs.pop("func")
    base_url = kwargs.pop("base_url")
    
    # Compute workspace_id from default workfile (same as other CLI commands)
    wf_path = default_workfile()
    workspace_id = compute_workspace_id(get_absolute_path(wf_path))
    
    func(args, base_url, workspace_id)
