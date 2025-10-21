#!/usr/bin/env python
import argparse
from importlib import import_module

def main():
    parser = argparse.ArgumentParser(prog="workforce", description="Workforce CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # register subcommands dynamically
    for name in ["gui", "runner", "server"]:
        module = import_module(f"workforce.{name}")
        subparser = subparsers.add_parser(name, help=f"{name} subcommand")
        module.add_arguments(subparser)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()

