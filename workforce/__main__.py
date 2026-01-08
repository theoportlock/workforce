#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
workforce — unified CLI entrypoint.
All GUI/RUN/EDIT/SERVER operations work with a single server instance
with dynamic port discovery and workspace routing by hashed file path.
"""

import argparse
import sys
import os

from workforce import utils
from workforce.utils import default_workfile, compute_workspace_id, get_workspace_url, get_absolute_path, ensure_workfile
from workforce.gui import main as gui_main
from workforce.run import main as run_main
from workforce.server import (
    cmd_start as server_cmd_start,
    cmd_stop as server_cmd_stop,
    cmd_list as server_cmd_list,
    start_server,
)
from workforce.edit import (
    cmd_add_node,
    cmd_add_edge,
    cmd_remove_node,
    cmd_remove_edge,
    cmd_edit_status,
    cmd_edit_wrapper
)
from workforce import __version__

# -----------------------------------------------------------------------------

def print_version():
    """Print version information."""
    print(f"Workforce version {__version__}")
    print(f"Python {sys.version}")

def main():
    # Handle --version flag at top level
    if '--version' in sys.argv or '-v' in sys.argv:
        print_version()
        return

    # Default behaviour: GUI with default workfile or temporary workfile in background
    if len(sys.argv) == 1:
        wf = ensure_workfile()
        ws_id = compute_workspace_id(wf)
        server_url = utils.resolve_server()
        base_url = f"{server_url}/workspace/{ws_id}"
        gui_main(base_url, wf_path=wf, workspace_id=ws_id, background=True)
        return

    parser = argparse.ArgumentParser(
        prog="workforce",
        description="Workforce - Visual workflow orchestration and execution"
    )
    parser.add_argument(
        '--version', '-v',
        action='store_true',
        help='Show version information and exit'
    )

    subparsers = parser.add_subparsers(dest="command", required=False)

    # ---------------- GUI ----------------
    gui_p = subparsers.add_parser("gui", help="Launch graphical interface")
    gui_p.add_argument("url_or_path", nargs="?", default=default_workfile(),
                       help="Workfile path or workspace URL (e.g., http://host:port/workspace/ws_abc123)")
    gui_p.add_argument("--foreground", "-f", action="store_true",
                       help="Run GUI in foreground (default: background)")
    def _gui(args):
        # Check if input is a workspace URL
        parsed = utils.parse_workspace_url(args.url_or_path) if args.url_or_path else None
        
        if parsed:
            # Direct workspace URL provided
            server_url, ws_id = parsed
            base_url = f"{server_url}/workspace/{ws_id}"
            # Use a placeholder workfile path (not used for remote access)
            wf_path = f"<remote:{ws_id}>"
            gui_main(base_url, wf_path=wf_path, workspace_id=ws_id, background=not args.foreground)
        elif args.url_or_path and utils.looks_like_url(args.url_or_path):
            # Looks like a URL but parsing failed - give helpful error
            print(f"Error: Invalid workspace URL format: {args.url_or_path}")
            print()
            print("Valid formats:")
            print("  http://host:port/workspace/ws_XXXXXXXX")
            print("  host:port/workspace/ws_XXXXXXXX")
            print()
            print("Note: Workspace IDs must start with 'ws_' followed by 8+ hex characters")
            print()
            print("To find your workspace URL, run on the server:")
            print("  wf server ls")
            sys.exit(1)
        else:
            # Traditional file path
            wf_path = ensure_workfile(args.url_or_path)
            ws_id = compute_workspace_id(wf_path)
            server_url = utils.resolve_server()
            base_url = f"{server_url}/workspace/{ws_id}"
            gui_main(base_url, wf_path=wf_path, workspace_id=ws_id, background=not args.foreground)
    gui_p.set_defaults(func=_gui)

    # ---------------- RUN ----------------
    run_p = subparsers.add_parser("run", help="Execute workflow")
    run_p.add_argument("url_or_path", nargs="?", default=default_workfile(),
                       help="Workfile path or workspace URL (e.g., http://host:port/workspace/ws_abc123)")
    run_p.add_argument("--nodes", nargs='*', help="Specific node IDs to run.")
    run_p.add_argument("--wrapper", default="{}", help="Command wrapper, use {} as placeholder for the command.")
    def _run(args):
        # Check if input is a workspace URL
        parsed = utils.parse_workspace_url(args.url_or_path) if args.url_or_path else None
        
        if parsed:
            # Direct workspace URL provided
            server_url, ws_id = parsed
            base_url = f"{server_url}/workspace/{ws_id}"
            wf_path = f"<remote:{ws_id}>"
            # Import here to avoid circular dependency
            from workforce.run.client import Runner
            runner = Runner(base_url, workspace_id=ws_id, workfile_path=wf_path, wrapper=args.wrapper)
            runner.start(initial_nodes=args.nodes)
        elif args.url_or_path and utils.looks_like_url(args.url_or_path):
            # Looks like a URL but parsing failed - give helpful error
            print(f"Error: Invalid workspace URL format: {args.url_or_path}")
            print()
            print("Valid formats:")
            print("  http://host:port/workspace/ws_XXXXXXXX")
            print("  host:port/workspace/ws_XXXXXXXX")
            print()
            print("Note: Workspace IDs must start with 'ws_' followed by 8+ hex characters")
            print()
            print("To find your workspace URL, run on the server:")
            print("  wf server ls")
            sys.exit(1)
        else:
            # Traditional file path
            wf_path = ensure_workfile(args.url_or_path)
            run_main(wf_path, nodes=args.nodes, wrapper=args.wrapper)
    run_p.set_defaults(func=_run)

    # ---------------- SERVER ----------------
    server_p = subparsers.add_parser("server", help="Manage the single machine-wide server")
    server_sub = server_p.add_subparsers(dest="server_command", required=True)

    # Start (background by default)
    sp = server_sub.add_parser("start", help="Start the server (background by default)")
    sp.add_argument("--foreground", action="store_true", help="Run in foreground instead of background")
    sp.add_argument("--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
    sp.set_defaults(func=lambda args: server_cmd_start(args))

    # Stop
    sp2 = server_sub.add_parser("stop", help="Stop the machine-wide server")
    sp2.set_defaults(func=lambda args: server_cmd_stop(args))

    # List (diagnostic)
    sp3 = server_sub.add_parser("ls", help="List active workspaces")
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
        wf_path = os.path.abspath(args.filename)
        ws_id = compute_workspace_id(wf_path)
        server_url = utils.resolve_server()
        base_url = f"{server_url}/workspace/{ws_id}"
        cmd_add_node(args, base_url, ws_id)
    en.set_defaults(func=_add_node)

    # --- remove-node ---
    ern = edit_sub.add_parser("remove-node")
    ern.add_argument("filename")
    ern.add_argument("node_id")
    def _remove_node(args):
        wf_path = os.path.abspath(args.filename)
        ws_id = compute_workspace_id(wf_path)
        server_url = utils.resolve_server()
        base_url = f"{server_url}/workspace/{ws_id}"
        cmd_remove_node(args, base_url, ws_id)
    ern.set_defaults(func=_remove_node)

    # --- add-edge ---
    ee = edit_sub.add_parser("add-edge")
    ee.add_argument("filename")
    ee.add_argument("source")
    ee.add_argument("target")
    def _add_edge(args):
        wf_path = os.path.abspath(args.filename)
        ws_id = compute_workspace_id(wf_path)
        server_url = utils.resolve_server()
        base_url = f"{server_url}/workspace/{ws_id}"
        cmd_add_edge(args, base_url, ws_id)
    ee.set_defaults(func=_add_edge)

    # --- remove-edge ---
    ere = edit_sub.add_parser("remove-edge")
    ere.add_argument("filename")
    ere.add_argument("source")
    ere.add_argument("target")
    def _remove_edge(args):
        wf_path = os.path.abspath(args.filename)
        ws_id = compute_workspace_id(wf_path)
        server_url = utils.resolve_server()
        base_url = f"{server_url}/workspace/{ws_id}"
        cmd_remove_edge(args, base_url, ws_id)
    ere.set_defaults(func=_remove_edge)

    # --- edit-status ---
    es = edit_sub.add_parser("edit-status")
    es.add_argument("filename")
    es.add_argument("element_type", choices=["node", "edge"])
    es.add_argument("element_id")
    es.add_argument("value")
    def _edit_status(args):
        wf_path = os.path.abspath(args.filename)
        ws_id = compute_workspace_id(wf_path)
        server_url = utils.resolve_server()
        base_url = f"{server_url}/workspace/{ws_id}"
        cmd_edit_status(args, base_url, ws_id)
    es.set_defaults(func=_edit_status)

    # --- edit-wrapper ---
    ew = edit_sub.add_parser("edit-wrapper")
    ew.add_argument("filename")
    ew.add_argument("wrapper")
    def _edit_wrapper(args):
        wf_path = os.path.abspath(args.filename)
        ws_id = compute_workspace_id(wf_path)
        server_url = utils.resolve_server()
        base_url = f"{server_url}/workspace/{ws_id}"
        cmd_edit_wrapper(args, base_url, ws_id)
    ew.set_defaults(func=_edit_wrapper)

    # Parse arguments and execute the corresponding function
    args = parser.parse_args()

    # Handle version flag if passed to parser
    if hasattr(args, 'version') and args.version:
        print_version()
        return

    # If no command provided, show help
    if not hasattr(args, 'func'):
        parser.print_help()
        return

    args.func(args)

# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()

