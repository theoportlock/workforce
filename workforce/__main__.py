#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
workforce — unified CLI entrypoint
Default: launch GUI with Workfile (if present) or fallback to get_default_workfile().
Subcommands: gui, run, server.
"""

import argparse
import sys
import os
from importlib import import_module

SUBCOMMANDS = ["gui", "run", "server", "edit"]
DEFAULT_WORKFILE = "Workfile"


def find_workfile():
    """Return the absolute path to Workfile in the current directory, or None."""
    path = os.path.join(os.getcwd(), DEFAULT_WORKFILE)
    return path if os.path.exists(path) else None


def launch_gui():
    """Launch GUI with Workfile if present, else the default workfile."""
    from workforce.gui import Gui

    workfile = find_workfile()
    Gui(workfile)


def build_parser():
    """Create the main argument parser and dynamically register subcommands."""
    parser = argparse.ArgumentParser(prog="workforce", description="Workforce CLI")
    subparsers = parser.add_subparsers(dest="command")

    for name in SUBCOMMANDS:
        module = import_module(f"workforce.{name}")
        subparser = subparsers.add_parser(name, help=f"{name} subcommand")
        if hasattr(module, "add_arguments"):
            module.add_arguments(subparser)
        subparser.set_defaults(func=getattr(module, "main", None))

    return parser


def main():
    # --- Case 1: No arguments — launch GUI automatically ---
    if len(sys.argv) == 1:
        launch_gui()
        return

    # --- Case 2: Subcommands / explicit arguments ---
    parser = build_parser()
    args = parser.parse_args()

    if not hasattr(args, "func") or args.func is None:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()

