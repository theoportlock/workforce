#!/usr/bin/env python

from .workforce_edit import gui
from .workforce_run import worker
from .workforce_view import plot_network
import argparse
import sys

def parse_args():
    parser = argparse.ArgumentParser(
        prog='workforce',
        description='Run a set of commands that are arranged in a GraphML network'
    )
    parser.add_argument("pipeline", help='Network file as a GraphML')
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-e", "--edit", action='store_true', help='Edit the network')
    group.add_argument("-r", "--run", action='store_true', help='Run the network')
    group.add_argument("-v", "--view", action='store_true', help='Visualise the network')
    return parser.parse_args()

def main():
    args = parse_args()
    if args.run:
        worker(args.pipeline)
    elif args.view:
        plot_network(args.pipeline)
    elif args.pipeline:
        gui(args.pipeline)
    else:
        gui()
    return 0


if __name__ == "__main__":
    sys.exit(main())

'''
#!/usr/bin/env python

import argparse
import sys
from .workforce_edit import gui
from .workforce_run import worker
from .workforce_view import plot_network

def main():
    parser = argparse.ArgumentParser(
        prog="workforce",
        description="Manage and run a GraphML-based workflow"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Edit subcommand
    edit_parser = subparsers.add_parser("edit", help="Edit the network")
    edit_parser.add_argument("pipeline", nargs="?", help="Network file as a GraphML")

    # Run subcommand
    run_parser = subparsers.add_parser("run", help="Run the network")
    run_parser.add_argument("pipeline", help="Network file as a GraphML")

    # View subcommand
    view_parser = subparsers.add_parser("view", help="Visualize the network")
    view_parser.add_argument("pipeline", help="Network file as a GraphML")

    args = parser.parse_args()

    if args.command == "run":
        worker(args.pipeline)
    elif args.command == "view":
        plot_network(args.pipeline)
    elif args.command == "edit":
        gui(args.pipeline if args.pipeline else None)

    return 0

if __name__ == "__main__":
    sys.exit(main())
'''
