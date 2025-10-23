#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
edit.py — GraphML editing CLI for Workforce.
Now delegates all edit logic to workforce.server to avoid circular imports.
"""

import argparse
from workforce import server


def add_arguments(subparsers):
    """Attach edit commands to the main CLI."""
    parser = subparsers.add_parser("edit", help="Modify Workfile nodes or edges")
    edit_sub = parser.add_subparsers(dest="action", required=True)

    # Add node
    p_add = edit_sub.add_parser("add-node", help="Add a new node")
    p_add.add_argument("filename")
    p_add.add_argument("--label", required=True)
    p_add.add_argument("--x", type=float, default=0.0)
    p_add.add_argument("--y", type=float, default=0.0)
    p_add.add_argument("--status", default="ready")
    p_add.set_defaults(func=lambda args: server.add_node(args.filename, args.label, args.x, args.y, args.status))

    # Remove node
    p_rm = edit_sub.add_parser("remove-node", help="Remove a node")
    p_rm.add_argument("filename")
    p_rm.add_argument("node_id")
    p_rm.set_defaults(func=lambda args: server.remove_node(args.filename, args.node_id))

    # Add edge
    p_edge = edit_sub.add_parser("add-edge", help="Add edge between two nodes")
    p_edge.add_argument("filename")
    p_edge.add_argument("source")
    p_edge.add_argument("target")
    p_edge.set_defaults(func=lambda args: server.add_edge(args.filename, args.source, args.target))

    # Remove edge
    p_redge = edit_sub.add_parser("remove-edge", help="Remove edge")
    p_redge.add_argument("filename")
    p_redge.add_argument("source")
    p_redge.add_argument("target")
    p_redge.set_defaults(func=lambda args: server.remove_edge(args.filename, args.source, args.target))

    # Edit status
    p_status = edit_sub.add_parser("edit-status", help="Edit node or edge status")
    p_status.add_argument("filename")
    p_status.add_argument("element_type", choices=["node", "edge"])
    p_status.add_argument("element_id")
    p_status.add_argument("value")
    p_status.set_defaults(func=lambda args: server.edit_status(args.filename, args.element_type, args.element_id, args.value))


def main():
    parser = argparse.ArgumentParser(description="Workforce GraphML Editor CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    add_arguments(subparsers)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

