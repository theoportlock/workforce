#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
edit.py — Command-line client for Workforce server API.
Performs remote edits via HTTP endpoints exposed by server.py.
"""

import argparse
import json
import os
import sys
import tempfile
import requests

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

def main():
    parser = argparse.ArgumentParser(description="Workforce Graph Editor CLI (client for server.py)")
    sub = parser.add_subparsers(dest="command", required=True)

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

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

