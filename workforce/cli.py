#!/usr/bin/env python

import argparse
import networkx as nx
from workforce.edit_element import edit_element_status
from workforce.run_node import run_node
from workforce.edit import gui

def edit(args):
    edit_element_status(args.filename, args.type, args.identifier, args.value)

def run(args):
    run_node(args.filename, args.node)

def launch_gui(args):
    gui(args.filename)

def main():
    parser = argparse.ArgumentParser(prog="workforce", description="Manage and run graph-based workflows.")
    subparsers = parser.add_subparsers(title="subcommands", dest="command")

    # Edit Command
    edit_parser = subparsers.add_parser("edit", help="Edit node/edge status in a GraphML file")
    edit_parser.add_argument("filename")
    edit_parser.add_argument("type", choices=["node", "edge"])
    edit_parser.add_argument("identifier")
    edit_parser.add_argument("value", choices=["run", "ran", "running", "to_run", "fail"])
    edit_parser.set_defaults(func=edit)

    # Run Command
    run_parser = subparsers.add_parser("run", help="Execute a command associated with a node")
    run_parser.add_argument("filename")
    run_parser.add_argument("node")
    run_parser.set_defaults(func=run)

    # GUI Command
    gui_parser = subparsers.add_parser("gui", help="Open the Dash-based workflow editor")
    gui_parser.add_argument("filename", nargs="?")
    gui_parser.set_defaults(func=launch_gui)

    args = parser.parse_args()

    if args.command:
        args.func(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()

