#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
workforce — unified CLI entrypoint
Default: launch GUI with Workfile (if present) or fallback to get_default_workfile().
Subcommands: gui, run, server, edit.
"""

import argparse
import sys
import os
from importlib import import_module

DEFAULT_WORKFILE = "Workfile"


def find_workfile():
    path = os.path.join(os.getcwd(), DEFAULT_WORKFILE)
    return path if os.path.exists(path) else None


def launch_gui():
    from workforce.gui import Gui
    workfile = find_workfile()
    Gui(workfile)


def main():
    # Case 1: no arguments → launch GUI
    if len(sys.argv) == 1:
        launch_gui()
        return

    # Top-level parser
    parser = argparse.ArgumentParser(prog="workforce", description="Workforce CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # ---------------- GUI ----------------
    gui_parser = subparsers.add_parser("gui", help="Launch graphical interface")
    gui_parser.add_argument("filename", help="GraphML file (defaults to Workfile)")
    gui_parser.set_defaults(func=lambda args: import_module("workforce.gui").main(args))

    # ---------------- RUN ----------------
    run_parser = subparsers.add_parser("run", help="Execute workflow nodes")
    run_parser.add_argument("filename", help="Workflow file (GraphML)")
    run_parser.add_argument("--prefix", default="", help="Command prefix")
    run_parser.add_argument("--suffix", default="", help="Command suffix")
    run_parser.set_defaults(func=lambda args: import_module("workforce.run").main(args))

    # ---------------- SERVER ----------------
    server_parser = subparsers.add_parser("server", help="Start workforce server")
    server_parser.add_argument("filename", help="Workflow file (GraphML)")
    server_parser.add_argument("--port", type=int, default=8000)
    server_parser.set_defaults(func=lambda args: import_module("workforce.server").main(args))

    # ---------------- EDIT ----------------
    edit_parser = subparsers.add_parser("edit", help="Edit running workflow via API")
    edit_sub = edit_parser.add_subparsers(dest="subcommand", required=True)

    # Add-node
    p_add = edit_sub.add_parser("add-node", help="Add node to graph")
    p_add.add_argument("filename", help="Workflow file (GraphML)")
    p_add.add_argument("label", help="Node label")
    p_add.add_argument("--x", type=float, default=0)
    p_add.add_argument("--y", type=float, default=0)
    p_add.add_argument("--status", default="")
    p_add.set_defaults(func=lambda args: import_module("workforce.edit").cmd_add_node(args))

    # Remove-node
    p_rmnode = edit_sub.add_parser("remove-node", help="Remove node by ID")
    p_rmnode.add_argument("filename", help="Workflow file (GraphML)")
    p_rmnode.add_argument("node_id")
    p_rmnode.set_defaults(func=lambda args: import_module("workforce.edit").cmd_remove_node(args))

    # Add-edge
    p_addedge = edit_sub.add_parser("add-edge", help="Add edge between nodes")
    p_addedge.add_argument("filename", help="Workfile file (GraphML)")
    p_addedge.add_argument("source")
    p_addedge.add_argument("target")
    p_addedge.set_defaults(func=lambda args: import_module("workforce.edit").cmd_add_edge(args))

    # Remove-edge
    p_rmedge = edit_sub.add_parser("remove-edge", help="Remove edge between nodes")
    p_rmedge.add_argument("filename", help="Workfile file (GraphML)")
    p_rmedge.add_argument("source")
    p_rmedge.add_argument("target")
    p_rmedge.set_defaults(func=lambda args: import_module("workforce.edit").cmd_remove_edge(args))

    # Edit-status
    p_status = edit_sub.add_parser("edit-status", help="Edit node/edge status")
    p_status.add_argument("filename", help="Workfile file (GraphML)")
    p_status.add_argument("element_type", choices=["node", "edge"])
    p_status.add_argument("element_id")
    p_status.add_argument("value", help="New status value")
    p_status.set_defaults(func=lambda args: import_module("workforce.edit").cmd_edit_status(args))

    # ---------------- PARSE & DISPATCH ----------------
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

