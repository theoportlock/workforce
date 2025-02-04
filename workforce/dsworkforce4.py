#!/usr/bin/env python3
import os
import subprocess
import networkx as nx
import argparse
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Parallel workflow executor")
    parser.add_argument("graphml", help="Input GraphML file")
    parser.add_argument("--jobs", "-j", type=int, default=os.cpu_count(), 
                      help="Number of parallel jobs")
    args = parser.parse_args()

    # Read graph and prepare dependency tracking
    G = nx.read_graphml(args.graphml)
    completed_file = Path(args.graphml + ".completed")
    completed_file.touch(exist_ok=True)
    
    # Build dependency map
    dependency_map = {
        node: set(G.predecessors(node))
        for node in G.nodes()
    }

    # Main processing loop
    while True:
        # Get completed nodes
        completed = set(completed_file.read_text().splitlines())
        
        # Find runnable nodes (all dependencies completed)
        runnable = [
            node for node, deps in dependency_map.items()
            if deps.issubset(completed) and node not in completed
        ]

        if not runnable:
            if len(completed) == len(G.nodes()):
                print("All nodes completed successfully!")
                break
            else:
                print("Deadlock detected - remaining nodes can't run!")
                break

        # Generate parallel commands
        commands = []
        for node in runnable:
            cmd = G.nodes[node].get('label', '')
            if cmd:
                # Command to run + append to completed file on success
                commands.append(
                    f"{cmd} && echo '{node}' >> {completed_file}"
                )

        # Execute in parallel using GNU Parallel
        parallel_cmd = [
            "parallel", "--halt", "now,fail=1", 
            "--jobs", str(args.jobs), "--tag", ":::"
        ] + commands
        
        try:
            subprocess.run(parallel_cmd, check=True)
        except subprocess.CalledProcessError:
            print("Failed tasks detected - aborting workflow")
            break

if __name__ == "__main__":
    main()
