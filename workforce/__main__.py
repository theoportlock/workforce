#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
workforce — unified CLI entrypoint.
All GUI/RUN/EDIT/SERVER operations work with a single server instance
with explicit host/port configuration and workspace routing by hashed file path.
"""

import argparse
import sys
import os
import json
import traceback

from workforce import utils
from workforce.utils import (
    default_workfile,
    compute_workspace_id,
    get_workspace_url,
    get_absolute_path,
    ensure_workfile,
    register_workspace,
)
from workforce.gui import main as gui_main
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
    # If running as frozen executable, wrap everything in error handling
    is_frozen = getattr(sys, 'frozen', False)
    
    if is_frozen:
        try:
            _main_impl()
        except Exception as e:
            # Show error in message box for frozen executables
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            error_msg = f"Workforce failed to start:\n\n{str(e)}\n\nTraceback:\n{traceback.format_exc()}"
            messagebox.showerror("Workforce Error", error_msg)
            root.destroy()
            sys.exit(1)
    else:
        _main_impl()

def _main_impl():
    is_frozen = getattr(sys, 'frozen', False)
    
    # Handle --version flag at top level
    if '--version' in sys.argv or '-v' in sys.argv:
        print_version()
        return

    # Default behaviour: GUI with default workfile or temporary workfile in background
    if len(sys.argv) == 1:
        wf = ensure_workfile()
        server_url = utils.resolve_server()
        registration = register_workspace(server_url, wf)
        ws_id = registration.get("workspace_id") or compute_workspace_id(wf)
        base_url = registration.get("url") or f"{server_url}/workspace/{ws_id}"
        # If running as frozen executable (PyInstaller), run in foreground to avoid subprocess issues
        gui_main(base_url, wf_path=wf, workspace_id=ws_id, background=(not is_frozen))
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
    gui_p.add_argument("--server-url", help="Server URL (overrides WORKFORCE_SERVER_URL, default http://127.0.0.1:5000)")
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
            server_url = utils.resolve_server(server_url=args.server_url)
            registration = register_workspace(server_url, wf_path)
            ws_id = registration.get("workspace_id") or compute_workspace_id(wf_path)
            base_url = registration.get("url") or f"{server_url}/workspace/{ws_id}"
            gui_main(base_url, wf_path=wf_path, workspace_id=ws_id, background=not args.foreground)
    gui_p.set_defaults(func=_gui)

    # ---------------- RUN ----------------
    run_p = subparsers.add_parser("run", help="Execute workflow")
    run_p.add_argument("url_or_path", nargs="?", default=default_workfile(),
                       help="Workfile path or workspace URL (e.g., http://host:port/workspace/ws_abc123)")
    run_p.add_argument("--nodes", nargs='*', help="Specific node IDs to run.")
    run_p.add_argument("--wrapper", default="{}", help="Command wrapper, use {} as placeholder for the command.")
    run_p.add_argument("--server-url", help="Server URL (overrides WORKFORCE_SERVER_URL, default http://127.0.0.1:5000)")
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
            server_url = utils.resolve_server(server_url=args.server_url)
            registration = register_workspace(server_url, wf_path)
            ws_id = registration.get("workspace_id") or compute_workspace_id(wf_path)
            base_url = registration.get("url") or f"{server_url}/workspace/{ws_id}"
            from workforce.run.client import Runner
            runner = Runner(base_url, workspace_id=ws_id, workfile_path=wf_path, wrapper=args.wrapper)
            runner.start(initial_nodes=args.nodes)
    run_p.set_defaults(func=_run)

    # ---------------- SERVER ----------------
    server_p = subparsers.add_parser("server", help="Manage the single machine-wide server")
    server_sub = server_p.add_subparsers(dest="server_command", required=True)

    # Start (background by default)
    sp = server_sub.add_parser("start", help="Start the server (background by default)")
    sp.add_argument("--foreground", action="store_true", help="Run in foreground instead of background")
    sp.add_argument("--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)")
    sp.add_argument("--port", type=int, default=5000, help="Port to bind to (default: 5000)")
    sp.add_argument("--log-dir", help="Directory for server.log (default: ~/.workforce)")
    sp.set_defaults(func=lambda args: server_cmd_start(args))

    # Stop
    sp2 = server_sub.add_parser("stop", help="Stop the machine-wide server")
    sp2.set_defaults(func=lambda args: server_cmd_stop(args))

    # List (diagnostic)
    sp3 = server_sub.add_parser("ls", help="List active workspaces")
    sp3.add_argument("--server-url", help="Server URL to query (default: current running server)")
    sp3.set_defaults(func=lambda args: server_cmd_list(args))

    # Add workspace registration
    sp4 = server_sub.add_parser("add", help="Register a workspace path with the running server")
    sp4.add_argument("path", help="Workfile path to register")
    sp4.add_argument("--host", default=None, help="Server host (overrides WORKFORCE_SERVER_URL)")
    sp4.add_argument("--port", type=int, default=None, help="Server port (overrides WORKFORCE_SERVER_URL)")
    def _server_add(args):
        server_url = None
        if args.host and args.port:
            server_url = f"http://{args.host}:{args.port}"
        registration = register_workspace(utils.resolve_server(server_url=server_url), ensure_workfile(args.path))
        print(f"workspace_id: {registration.get('workspace_id')}")
        print(f"url: {registration.get('url')}")
    sp4.set_defaults(func=_server_add)

    # Remove workspace
    sp5 = server_sub.add_parser("rm", help="Remove a workspace from the running server")
    sp5.add_argument("workspace_id", help="Workspace ID to remove")
    sp5.add_argument("--host", default=None, help="Server host (overrides WORKFORCE_SERVER_URL)")
    sp5.add_argument("--port", type=int, default=None, help="Server port (overrides WORKFORCE_SERVER_URL)")
    def _server_rm(args):
        server_url = None
        if args.host and args.port:
            server_url = f"http://{args.host}:{args.port}"
        server_url = utils.resolve_server(server_url=server_url, start_if_missing=False)
        result = utils.remove_workspace(server_url, args.workspace_id)
        import json
        print(json.dumps(result))
    sp5.set_defaults(func=_server_rm)

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
        wf_path = ensure_workfile(args.filename)
        server_url = utils.resolve_server()
        registration = register_workspace(server_url, wf_path)
        ws_id = registration.get("workspace_id") or compute_workspace_id(wf_path)
        base_url = registration.get("url") or f"{server_url}/workspace/{ws_id}"
        cmd_add_node(args, base_url, ws_id)
    en.set_defaults(func=_add_node)

    # --- remove-node ---
    ern = edit_sub.add_parser("remove-node")
    ern.add_argument("filename")
    ern.add_argument("node_id")
    def _remove_node(args):
        wf_path = ensure_workfile(args.filename)
        server_url = utils.resolve_server()
        registration = register_workspace(server_url, wf_path)
        ws_id = registration.get("workspace_id") or compute_workspace_id(wf_path)
        base_url = registration.get("url") or f"{server_url}/workspace/{ws_id}"
        cmd_remove_node(args, base_url, ws_id)
    ern.set_defaults(func=_remove_node)

    # --- add-edge ---
    ee = edit_sub.add_parser("add-edge")
    ee.add_argument("filename")
    ee.add_argument("source")
    ee.add_argument("target")
    def _add_edge(args):
        wf_path = ensure_workfile(args.filename)
        server_url = utils.resolve_server()
        registration = register_workspace(server_url, wf_path)
        ws_id = registration.get("workspace_id") or compute_workspace_id(wf_path)
        base_url = registration.get("url") or f"{server_url}/workspace/{ws_id}"
        cmd_add_edge(args, base_url, ws_id)
    ee.set_defaults(func=_add_edge)

    # --- remove-edge ---
    ere = edit_sub.add_parser("remove-edge")
    ere.add_argument("filename")
    ere.add_argument("source")
    ere.add_argument("target")
    def _remove_edge(args):
        wf_path = ensure_workfile(args.filename)
        server_url = utils.resolve_server()
        registration = register_workspace(server_url, wf_path)
        ws_id = registration.get("workspace_id") or compute_workspace_id(wf_path)
        base_url = registration.get("url") or f"{server_url}/workspace/{ws_id}"
        cmd_remove_edge(args, base_url, ws_id)
    ere.set_defaults(func=_remove_edge)

    # --- edit-status ---
    es = edit_sub.add_parser("edit-status")
    es.add_argument("filename")
    es.add_argument("element_type", choices=["node", "edge"])
    es.add_argument("element_id")
    es.add_argument("value")
    def _edit_status(args):
        wf_path = ensure_workfile(args.filename)
        server_url = utils.resolve_server()
        registration = register_workspace(server_url, wf_path)
        ws_id = registration.get("workspace_id") or compute_workspace_id(wf_path)
        base_url = registration.get("url") or f"{server_url}/workspace/{ws_id}"
        cmd_edit_status(args, base_url, ws_id)
    es.set_defaults(func=_edit_status)

    # --- edit-wrapper ---
    ew = edit_sub.add_parser("edit-wrapper")
    ew.add_argument("filename")
    ew.add_argument("wrapper")
    def _edit_wrapper(args):
        wf_path = ensure_workfile(args.filename)
        server_url = utils.resolve_server()
        registration = register_workspace(server_url, wf_path)
        ws_id = registration.get("workspace_id") or compute_workspace_id(wf_path)
        base_url = registration.get("url") or f"{server_url}/workspace/{ws_id}"
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

