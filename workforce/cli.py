#!/usr/bin/env python
"""Console script for workforce."""
import argparse
import sys

def main():
    from .workforce import worker
    from .gui import gui
    parser = argparse.ArgumentParser()
    parser.add_argument("-r", "--run")
    parser.add_argument("workflow")
    args = parser.parse_args()
    if args.run:
        current_worker = worker(args.run)
        current_worker.run()
    elif args.workflow:
        gui(args.workflow)
    else:
        gui()
    return 0


if __name__ == "__main__":
    sys.exit(main())
