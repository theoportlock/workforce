#!/usr/bin/env python3
"""
Script to cleanup lingering workspaces from test runs.

Usage:
    python scripts/cleanup_workspaces.py [--force]

This script:
1. Lists all active workspaces
2. Identifies workspaces with missing files (likely from temp fixtures)
3. Sends disconnect requests to cleanup lingering workspaces
"""

import sys
import os
import requests
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from workforce.utils import get_running_server


def cleanup_lingering_workspaces(force=False):
    """Cleanup workspaces from test runs."""
    
    # Find running server
    server_info = get_running_server()
    if not server_info:
        print("No server running. Nothing to cleanup.")
        return 0
    
    host, port, _pid = server_info
    server_url = f"http://{host}:{port}"
    print(f"Found server at: {server_url}")
    
    # Get active workspaces
    resp = requests.get(f"{server_url}/workspaces")
    workspaces = resp.json().get("workspaces", [])
    
    if not workspaces:
        print("No active workspaces found.")
        return 0
    
    print(f"\nFound {len(workspaces)} active workspace(s):\n")
    
    to_cleanup = []
    for ws in workspaces:
        ws_id = ws["workspace_id"]
        path = ws["workfile_path"]
        clients = ws["client_count"]
        exists = os.path.exists(path)
        
        print(f"  {ws_id}:")
        print(f"    File:    {path}")
        print(f"    Clients: {clients}")
        print(f"    Exists:  {exists}")
        
        # Mark for cleanup if file doesn't exist (likely temp file)
        if not exists:
            to_cleanup.append((ws_id, path, clients))
            print(f"    ⚠️  File missing - marking for cleanup")
        print()
    
    if not to_cleanup:
        print("All workspaces have valid files. Nothing to cleanup.")
        return 0
    
    print(f"\n{len(to_cleanup)} workspace(s) marked for cleanup.")
    
    if not force:
        response = input("Disconnect clients and cleanup these workspaces? [y/N] ")
        if response.lower() not in ['y', 'yes']:
            print("Cleanup cancelled.")
            return 1
    
    # Cleanup workspaces
    print("\nCleaning up workspaces...")
    for ws_id, path, clients in to_cleanup:
        print(f"  Disconnecting {clients} client(s) from {ws_id}...", end=" ")
        try:
            for _ in range(clients):
                resp = requests.post(
                    f"{server_url}/workspace/{ws_id}/client-disconnect",
                    json={}
                )
                if resp.status_code == 200:
                    print("✓", end="")
                else:
                    print(f"✗ (HTTP {resp.status_code})", end="")
            print()
        except requests.exceptions.ConnectionError:
            # Server may have shut down after last disconnect
            print(" (server shutdown)")
            break
        except Exception as e:
            print(f" ✗ Error: {e}")
    
    print("\nCleanup complete!")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cleanup lingering workspaces")
    parser.add_argument("--force", action="store_true", 
                       help="Skip confirmation prompt")
    args = parser.parse_args()
    
    sys.exit(cleanup_lingering_workspaces(force=args.force))
