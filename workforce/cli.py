#!/usr/bin/env python
"""Console script for workforce."""
import argparse
import sys

def main():
    from .workforce import worker
    from .gui import gui
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.plan:
        current_worker = worker(args.plan[0])
        current_worker.run()
    else:
        gui()
    return 0


if __name__ == "__main__":
    sys.exit(main())
