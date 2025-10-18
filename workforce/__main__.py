#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
import subprocess
import sys
import time
from . import gui
from . import workforce
from . import server


def run_node_cmd(args):
    workforce.run_node(args.filename, args.node, args.prefix, args.suffix)

def run_tasks_cmd(args):
    workforce.worker(args.filename, args.prefix, args.suffix, args.speed)

def gui_cmd(args):
    gui.Gui(args.filename)


def parse_args():
    """Create and parse CLI arguments, applying default fallback logic."""
    valid_commands = {"run", "run_node", "gui", "-h", "--help"}

    # Auto-insert 'gui' when no valid subcommand is given
    if len(sys.argv) == 1:
        if os.path.exists("Workfile"):
            sys.argv.extend(["gui", "Workfile"])
        else:
            sys.argv.append("gui")
    elif sys.argv[1] not in valid_commands:
        sys.argv.insert(1, "gui")

    parser = argparse.ArgumentParser(
        prog="workforce",
        description="Manage and run graph-based workflows."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Run Tasks Command
    run_parser = subparsers.add_parser("run", help="Run all scheduled workflow tasks")
    run_parser.add_argument("filename", help="GraphML file containing tasks")
    run_parser.add_argument("--prefix", '-p', default='', help="Prefix for node execution")
    run_parser.add_argument("--suffix", '-s', default='', help="Suffix for node execution")
    run_parser.add_argument("--run_task", action="store_true", help="Run a single task and exit")
    run_parser.add_argument("--speed", type=float, default=1, help="Seconds in between job submission")
    run_parser.set_defaults(func=run_tasks_cmd)

    # Run Single Node Command
    run_node_parser = subparsers.add_parser("run_node", help="Run a single node in the workflow")
    run_node_parser.add_argument("filename", help="Path to the input GraphML file.")
    run_node_parser.add_argument("node", help="Node to execute.")
    run_node_parser.add_argument("--prefix", '-p', default='', help="Prefix for command execution.")
    run_node_parser.add_argument("--suffix", '-s', default='', help="Suffix for command execution.")
    run_node_parser.set_defaults(func=run_node_cmd)

    # GUI Command
    gui_parser = subparsers.add_parser("gui", help="Launch the GUI")
    gui_parser.add_argument("filename", nargs="?", default="Workfile.graphml",
                            help="Optional GraphML file to load (default: Workfile.graphml)")
    gui_parser.set_defaults(func=gui_cmd)

    return parser.parse_args()


def main():
    args = parse_args()

    filename = args.filename
    abs_filename = os.path.abspath(filename)
    lockfile = server.get_lockfile(abs_filename)

    # Start background server if not already running
    if not os.path.exists(lockfile):
        server_path = os.path.join(os.path.dirname(__file__), "server.py")
        subprocess.Popen([sys.executable, server_path])
        time.sleep(1)  # brief pause for startup

    args.func(args)

if __name__ == "__main__":
    main()

