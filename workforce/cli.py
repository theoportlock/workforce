#!/usr/bin/env python
"""Console script for workforce."""
import argparse
import sys

def main():
    from .workforce import worker
    """Console script for workforce."""
    parser = argparse.ArgumentParser()
    parser.add_argument("-g", "--graph", action='store_true')
    parser.add_argument("plan", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.plan:
        current_worker = worker(args.plan[0])
        if args.graph:
            current_worker.graph()
        else:
            current_worker.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
