#!/usr/bin/env python

import argparse
from workforce.edit_element import edit_element_status
from workforce.run_node import run_node
from workforce.run import worker
from workforce.view import plot_network
from workforce.edit import gui

def edit(args):
    edit_element_status(args.filename, args.type, args.identifier, args.value)

def run_node_cmd(args):
    run_node(args.filename, args.node, args.prefix)

def run_tasks_cmd(args):
    worker(args.filename, args.prefix, args.speed)

def view(args):
    plot_network(args.filename)

def launch_gui(args):
    gui(args.filename)

def main():
    parser = argparse.ArgumentParser(
        prog="workforce", 
        description="Manage and run graph-based workflows."
    )
    
    subparsers = parser.add_subparsers(dest="command", required=False)

    # Edit Command
    edit_parser = subparsers.add_parser("edit", help="Edit node/edge status in a GraphML file")
    edit_parser.add_argument("filename", help="GraphML file to edit")
    edit_parser.add_argument("type", choices=["node", "edge"], help="Element type to edit")
    edit_parser.add_argument("identifier", help="Identifier of the element")
    edit_parser.add_argument("value", choices=["run", "ran", "running", "to_run", "fail"],
                             help="New status value")
    edit_parser.set_defaults(func=edit)

    # Run Tasks Command
    run_parser = subparsers.add_parser("run", help="Run all scheduled workflow tasks")
    run_parser.add_argument("filename", help="GraphML file containing tasks")
    run_parser.add_argument("--prefix", '-p', default='bash -c', type=str, help="Prefix for node execution")
    run_parser.add_argument("--run_task", action="store_true", help="Run a single task and exit")
    run_parser.add_argument("--speed", type=float, default=0.5, help="Seconds inbetween job submission")
    run_parser.set_defaults(func=run_tasks_cmd)

    # Run Single Node Command
    run_node_parser = subparsers.add_parser("run_node", help="Run a single node in the workflow")
    run_node_parser.add_argument("filename", type=str, help="Path to the input GraphML file.")
    run_node_parser.add_argument("node", type=str, help="Node to execute.")
    run_node_parser.add_argument("--prefix", '-p', default='bash -c', required=False, type=str, help="Prefix for command execution.")
    run_node_parser.set_defaults(func=run_node_cmd)

    # View Command
    view_parser = subparsers.add_parser("view", help="Visualize the GraphML workflow")
    view_parser.add_argument("filename", help="GraphML file to visualize")
    view_parser.set_defaults(func=view)

    # GUI Command
    gui_parser = subparsers.add_parser("gui", help="Open the Dash-based workflow editor")
    gui_parser.add_argument("filename", nargs="?", default=None, help="GraphML file for the GUI")
    gui_parser.set_defaults(func=launch_gui)

    # Handle default behavior when no subcommand is given
    args = parser.parse_args()

    if args.command is None:
        launch_gui(args)
    else:
        args.func(args)

if __name__ == "__main__":
    main()
