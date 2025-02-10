#!/usr/bin/env python

import argparse
import networkx as nx
from filelock import FileLock

# Allowed status values
ALLOWED_VALUES = {"run", "ran", "running", "to_run", "fail"}

def edit_element_status(filename, element_type, element_id, value):
    """
    Edit the 'status' attribute of a node or edge in a GraphML file.

    Args:
        filename (str): Path to GraphML file
        element_type (str): 'node' or 'edge'
        element_id (str or tuple): Node ID or (source, target) tuple for edges
        value (str): New value for the 'status' attribute (must be in ALLOWED_VALUES)
    """
    if value not in ALLOWED_VALUES:
        raise ValueError(f"Invalid status '{value}'. Allowed values: {ALLOWED_VALUES}")

    with FileLock(f"{filename}.lock"):
        G = nx.read_graphml(filename)

        try:
            if element_type == 'node':
                if element_id not in G.nodes:
                    raise ValueError(f"Node '{element_id}' not found in graph")
                G.nodes[element_id]['status'] = value

            elif element_type == 'edge':
                if element_id not in G.edges:
                    raise ValueError(f"Edge '{element_id}' not found in graph")
                G.edges[element_id]['status'] = value

            else:
                raise ValueError("Element type must be 'node' or 'edge'")

            nx.write_graphml(G, filename)

        except ValueError as e:
            print(f"Error: {e}")

def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Edit node/edge status in a GraphML file",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("filename", help="Path to GraphML file")
    parser.add_argument("type", choices=['node', 'edge'], help="Element type to modify")
    parser.add_argument("identifier", help="Node ID (str) or Edge ID ('source,target')")
    parser.add_argument("value", choices=ALLOWED_VALUES, help="New status value")
    return parser.parse_args()

def process_arguments(args):
    """Process command-line arguments."""
    element_type = args.type

    # Convert edge identifier from "source,target" to tuple
    if element_type == 'edge':
        element_id = tuple(args.identifier.split(","))
    else:
        element_id = args.identifier

    return element_id, args.value

def main():
    args = parse_arguments()
    try:
        element_id, value = process_arguments(args)
        main(args.filename, args.type, element_id, value)
    except Exception as e:
        print(f"Operation failed: {str(e)}")
        exit(1)

if __name__ == "__main__":
    main()
