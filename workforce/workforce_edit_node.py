#!/usr/bin/env python
import os
import time
import subprocess
import networkx as nx
from filelock import FileLock
import argparse

def edit(filename, obj, status):
    with FileLock(f"{filename}.lock"):
        G = nx.read_graphml(filename)
        node_status = nx.get_node_attributes(G, "status")
        nx.write_graphml(G, filename)
        if not nx.get_node_attributes(G, "status"):

def parse_arguments():
    parser = argparse.ArgumentParser(description="Schedule tasks with a GraphML file")
    parser.add_argument("filename", type=str, help="Path to the input GraphML file.")
    parser.add_argument("node", type=str, help="Item to edit.")
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_arguments()
    schedule_tasks(args.filename)



#!/usr/bin/env python
import argparse
import networkx as nx
from filelock import FileLock
import ast

def edit_graph_attribute(filename, element_type, element_id, attribute, value):
    """
    Edit an attribute of a node or edge in a GraphML file.

    Args:
        filename (str): Path to GraphML file
        element_type (str): 'node' or 'edge'
        element_id (str or tuple): Node ID or (source, target) tuple for edges
        attribute (str): Attribute name to modify
        value (any): New value for the attribute
    """
    with FileLock(f"{filename}.lock"):
        G = nx.read_graphml(filename)

        try:
            if element_type == 'node':
                if element_id not in G.nodes:
                    raise ValueError(f"Node {element_id} not found in graph")
                G.nodes[element_id][attribute] = value
            elif element_type == 'edge':
                if element_id not in G.edges:
                    raise ValueError(f"Edge {element_id} not found in graph")
                G.edges[element_id][attribute] = value
            else:
                raise ValueError("Element type must be 'node' or 'edge'")

            nx.write_graphml(G, filename)
            print(f"Updated {element_type} {element_id}: {attribute} = {value}")

        except Exception as e:
            print(f"Error updating attribute: {str(e)}")
            raise

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Edit node/edge attributes in a GraphML file",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument("filename", help="Path to GraphML file")
    parser.add_argument("type", choices=['node', 'edge'],
                      help="Type of element to modify")
    parser.add_argument("identifier", nargs='+',
                      help="Node ID or space-separated source/target for edges")
    parser.add_argument("attribute", help="Attribute name to modify")
    parser.add_argument("value", help="New value for the attribute")

    return parser.parse_args()

def process_arguments(args):
    # Try to convert value to Python literal
    try:
        value = ast.literal_eval(args.value)
    except (ValueError, SyntaxError):
        value = args.value  # Keep as string if conversion fails

    # Process identifier based on element type
    if args.type == 'node':
        element_id = args.identifier[0]
    else:  # edge
        if len(args.identifier) != 2:
            raise ValueError("Edge requires source and target identifiers")
        element_id = tuple(args.identifier)

    return element_id, value

if __name__ == "__main__":
    args = parse_arguments()
    try:
        element_id, value = process_arguments(args)
        edit_graph_attribute(
            args.filename,
            args.type,
            element_id,
            args.attribute,
            value
        )
    except Exception as e:
        print(f"Operation failed: {str(e)}")
        exit(1)
