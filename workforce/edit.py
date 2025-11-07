#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
edit.py — Command-line client for Workforce server API.
Performs remote edits via HTTP endpoints exposed by server.py.
"""

import argparse
import sys

from workforce.utils import load_registry, REGISTRY_PATH, resolve_port, send_request


def cmd_add_node(args):
    _, port = resolve_port(args.file)
    payload = {
        "label": args.label,
        "x": args.x,
        "y": args.y,
        "status": args.status,
    }
    send_request(port, "add-node", payload)


def cmd_remove_node(args):
    _, port = resolve_port(args.file)
    send_request(port, "remove-node", {"node_id": args.node_id})


def cmd_add_edge(args):
    _, port = resolve_port(args.file)
    send_request(port, "add-edge", {"source": args.source, "target": args.target})


def cmd_remove_edge(args):
    _, port = resolve_port(args.file)
    send_request(port, "remove-edge", {"source": args.source, "target": args.target})


def cmd_edit_status(args):
    _, port = resolve_port(args.file)
    send_request(port, "edit-status", {
        "element_type": args.element_type,
        "element_id": args.element_id,
        "value": args.value,
    })


# === CLI Parser ===

# New: allow integration into the top-level CLI by registering subcommands
def add_arguments(parent_parser):
    """
    Register edit subcommands on the provided parent_parser (the 'workforce edit' subparser).
    """
    sub = parent_parser.add_subparsers(dest="command", required=True)

    # add-node
    p_add = sub.add_parser("add-node", help="Add a new node to the graph")
    p_add.add_argument("label", help="Node label")
    p_add.add_argument("--x", type=float, default=0)
    p_add.add_argument("--y", type=float, default=0)
    p_add.add_argument("--status", default="")
    p_add.add_argument("--file", help="GraphML file (to find correct server)")
    p_add.set_defaults(func=cmd_add_node)

    # remove-node
    p_rmnode = sub.add_parser("remove-node", help="Remove a node")
    p_rmnode.add_argument("node_id", help="Node ID")
    p_rmnode.add_argument("--file", help="GraphML file")
    p_rmnode.set_defaults(func=cmd_remove_node)

    # add-edge
    p_addedge = sub.add_parser("add-edge", help="Add edge between nodes")
    p_addedge.add_argument("source", help="Source node ID")
    p_addedge.add_argument("target", help="Target node ID")
    p_addedge.add_argument("--file", help="GraphML file")
    p_addedge.set_defaults(func=cmd_add_edge)

    # remove-edge
    p_rmedge = sub.add_parser("remove-edge", help="Remove edge between nodes")
    p_rmedge.add_argument("source", help="Source node ID")
    p_rmedge.add_argument("target", help="Target node ID")
    p_rmedge.add_argument("--file", help="GraphML file")
    p_rmedge.set_defaults(func=cmd_remove_edge)

    # edit-status
    p_status = sub.add_parser("edit-status", help="Edit status of node or edge")
    p_status.add_argument("element_type", choices=["node", "edge"])
    p_status.add_argument("element_id")
    p_status.add_argument("value", help="New status value")
    p_status.add_argument("--file", help="GraphML file")
    p_status.set_defaults(func=cmd_edit_status)


def main(args=None):
    """
    Entrypoint for edit command.

    - When imported and used under workforce.__main__, __main__ will call args.func(args) directly,
      but workforce.__main__ also sets a default func to this module.main for top-level 'edit' parser,
      so main must accept an args Namespace.
    - When invoked directly (python -m workforce.edit or python edit.py), call with no args to parse argv.
    """
    if args is None:
        parser = argparse.ArgumentParser(description="Workforce Graph Editor CLI (client for server.py)")
        add_arguments(parser)
        parsed = parser.parse_args()
        parsed.func(parsed)
        return

    # args provided by top-level parser integration
    # If an inner subparser set func (e.g. cmd_add_node), call it.
    if hasattr(args, "func") and callable(args.func) and args.func is not main:
        args.func(args)
        return

    # No inner command was selected; show help for edit subcommand
    helper = argparse.ArgumentParser(prog="workforce edit", description="Workforce edit subcommands")
    add_arguments(helper)
    helper.print_help()
    sys.exit(1)


if __name__ == "__main__":
    main()

