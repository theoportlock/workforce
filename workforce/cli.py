#!/usr/bin/env python
"""Console script for workforce."""
import argparse
import sys

def main():
    from .workforce import worker
    from .gui import gui
    parser = argparse.ArgumentParser()
    parser.add_argument("-r", "--run", required=False)
    parser.add_argument("pipeline", nargs='?')
    args = parser.parse_args()
    if args.run:
        worker(args.run)
    elif args.pipeline:
        gui(args.pipeline)
    else:
        gui()
    return 0


if __name__ == "__main__":
    sys.exit(main())
