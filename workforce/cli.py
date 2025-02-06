#!/usr/bin/env python
"""Console script for workforce."""
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
    parser.add_argument("pipeline", nargs='?', help='Network file as a GraphML')
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
        plot_network(args.pipeline, args.pipeline+'.pdf')
    elif args.pipeline:
        gui(args.pipeline)
    else:
        gui()
    return 0


if __name__ == "__main__":
    sys.exit(main())
