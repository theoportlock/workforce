#!/usr/bin/env python

from . import gui
from . import workforce
import argparse
import os
import sys

def run_node_cmd(args):
    workforce.run_node(args.filename, args.node, args.prefix, args.suffix)

def run_tasks_cmd(args):
    workforce.worker(args.filename, args.prefix, args.suffix, args.speed)

def gui_cmd(args):
    gui.Gui(args.filename)  # Pass only the filename, not the entire Namespace

def main():
    valid_commands = {"run", "run_node", "gui", "-h", "--help"}

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

    subparsers = parser.add_subparsers(dest="command")

    # (rest of your code remains the same)

    # Run Tasks Command
    run_parser = subparsers.add_parser("run", help="Run all scheduled workflow tasks")
    run_parser.add_argument("filename", help="GraphML file containing tasks")
    run_parser.add_argument("--prefix", '-p', default='', type=str, help="Prefix for node execution")
    run_parser.add_argument("--suffix", '-s', default='', type=str, help="Suffix for node execution")
    run_parser.add_argument("--run_task", action="store_true", help="Run a single task and exit")
    run_parser.add_argument("--speed", type=float, default=1, help="Seconds in between job submission")
    run_parser.set_defaults(func=run_tasks_cmd)

    # Run Single Node Command
    run_node_parser = subparsers.add_parser("run_node", help="Run a single node in the workflow")
    run_node_parser.add_argument("filename", type=str, help="Path to the input GraphML file.")
    run_node_parser.add_argument("node", type=str, help="Node to execute.")
    run_node_parser.add_argument("--prefix", '-p', default='', required=False, type=str, help="Prefix for command execution.")
    run_node_parser.add_argument("--suffix", '-s', default='', required=False, type=str, help="Suffix for command execution.")
    run_node_parser.set_defaults(func=run_node_cmd)

    # GUI Command
    gui_parser = subparsers.add_parser("gui", help="Launch the GUI")
    gui_parser.add_argument("filename", nargs="?", help="Optional GraphML file to load")
    gui_parser.set_defaults(func=gui_cmd)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
