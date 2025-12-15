#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
workforce — unified CLI entrypoint.
All GUI/RUN/EDIT operations resolve either a URL or a filename into
an active server URL automatically using utils.resolve_target().
"""

import argparse
import sys

from workforce.utils import default_workfile, resolve_target
from workforce.gui import main as gui_main
from workforce.run import main as run_main
from workforce.server import (
    cmd_start as server_cmd_start,
    cmd_stop as server_cmd_stop,
    cmd_list as server_cmd_list,
)
from workforce.edit import (
    cmd_add_node,
    cmd_add_edge,
    cmd_remove_node,
    cmd_remove_edge,
    cmd_edit_status,
    cmd_edit_wrapper
)
from workforce.gui import main as gui_main

# -----------------------------------------------------------------------------

def main():
    # Default behaviour: GUI with default workfile
    if len(sys.argv) == 1:
        gui_main(resolve_target(default_workfile()))
        return

    parser = argparse.ArgumentParser(prog="workforce", description="Workforce CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # ---------------- GUI ----------------
    gui_p = subparsers.add_parser("gui", help="Launch graphical interface")
    gui_p.add_argument("url_or_path", nargs="?", default=default_workfile())
    gui_p.set_defaults(func=lambda args: gui_main(resolve_target(args.url_or_path)))

    # ---------------- RUN ----------------
    run_p = subparsers.add_parser("run", help="Execute workflow")
    run_p.add_argument("url_or_path", nargs="?", default=default_workfile())
    run_p.add_argument("--nodes", nargs='*', help="Specific node IDs to run.")
    run_p.add_argument("--subset-only", action="store_true", help="Only run specified nodes, not their descendants.")
    run_p.add_argument("--wrapper", default="{}", help="Command wrapper, use {} as placeholder for the command.")
    run_p.set_defaults(func=lambda args: run_main(
        resolve_target(args.url_or_path),
        nodes=args.nodes,
        wrapper=args.wrapper,
        subset_only=args.subset_only
    ))

    # ---------------- SERVER ----------------
    server_p = subparsers.add_parser("server", help="Manage servers")
    server_sub = server_p.add_subparsers(dest="server_command", required=True)

    # Start
    sp = server_sub.add_parser("start", help="Start a server")
    sp.add_argument("filename", nargs="?", default=default_workfile())
    sp.add_argument("--foreground", "-f", action="store_true")
    sp.add_argument("--port", type=int)
    sp.set_defaults(func=lambda args: server_cmd_start(args))

    # Stop
    sp2 = server_sub.add_parser("stop", help="Stop a server")
    sp2.add_argument("filename", nargs="?", default=default_workfile())
    sp2.set_defaults(func=lambda args: server_cmd_stop(args))

    # List
    sp3 = server_sub.add_parser("ls", help="List active servers")
    sp3.set_defaults(func=lambda args: server_cmd_list(args))

    # ---------------- EDIT ----------------
    edit_p = subparsers.add_parser("edit", help="Edit workflow graph via API")
    edit_sub = edit_p.add_subparsers(dest="edit_cmd", required=True)


    # --- add-node ---
    en = edit_sub.add_parser("add-node")
    en.add_argument("filename")
    en.add_argument("label")
    en.add_argument("--x", type=float, default=0)
    en.add_argument("--y", type=float, default=0)
    en.add_argument("--status", default="")
    def _add_node(args):
        url = resolve_target(args.filename)
        cmd_add_node(args, url)
    en.set_defaults(func=_add_node)


    # --- remove-node ---
    ern = edit_sub.add_parser("remove-node")
    ern.add_argument("filename")
    ern.add_argument("node_id")
    def _remove_node(args):
        url = resolve_target(args.filename)
        cmd_remove_node(args, url)
    ern.set_defaults(func=_remove_node)


    # --- add-edge ---
    ee = edit_sub.add_parser("add-edge")
    ee.add_argument("filename")
    ee.add_argument("source")
    ee.add_argument("target")
    def _add_edge(args):
        url = resolve_target(args.filename)
        cmd_add_edge(args, url)
    ee.set_defaults(func=_add_edge)


    # --- remove-edge ---
    ere = edit_sub.add_parser("remove-edge")
    ere.add_argument("filename")
    ere.add_argument("source")
    ere.add_argument("target")
    def _remove_edge(args):
        url = resolve_target(args.filename)
        cmd_remove_edge(args, url)
    ere.set_defaults(func=_remove_edge)


    # --- edit-status ---
    es = edit_sub.add_parser("edit-status")
    es.add_argument("filename")
    es.add_argument("element_type", choices=["node", "edge"])
    es.add_argument("element_id")
    es.add_argument("value")
    def _edit_status(args):
        url = resolve_target(args.filename)
        cmd_edit_status(args, url)
    es.set_defaults(func=_edit_status)


    # --- edit-wrapper ---
    ew = edit_sub.add_parser("edit-wrapper")
    ew.add_argument("filename")
    ew.add_argument("wrapper")
    def _edit_wrapper(args):
        url = resolve_target(args.filename)
        cmd_edit_wrapper(args, url)
    ew.set_defaults(func=_edit_wrapper)

    # Parse arguments and execute the corresponding function
    args = parser.parse_args()
    args.func(args)


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
