"""
Recent files management for Workforce GUI.

Maintains a persistent list of recently opened workflow files using the
system user data directory via platformdirs, ensuring cross-platform compatibility.
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Optional

import platformdirs


class RecentFileManager:
    """Manages persistent recent workflow files list."""

    MAX_RECENT = 20
    RECENT_FILE = "recent.json"

    def __init__(self):
        """Initialize recent file manager with user data directory."""
        app_data_dir = platformdirs.user_data_dir(appname="workforce", appauthor="workforce")
        self.data_dir = Path(app_data_dir)
        self.recent_path = self.data_dir / self.RECENT_FILE

    def load(self) -> List[str]:
        """
        Load recent files list from JSON file.

        Returns:
            List of recent file paths (absolute paths), empty list if file doesn't exist.
        """
        if not self.recent_path.exists():
            return []

        try:
            with open(self.recent_path, "r") as f:
                data = json.load(f)
                return data.get("recent_files", [])
        except (json.JSONDecodeError, OSError):
            return []

    def _load_data(self) -> Dict:
        """
        Internal: Load full recent data dict, handling missing/corrupted files.

        Returns:
            Dict with keys 'recent_files' and optionally 'recent_remotes'.
        """
        if not self.recent_path.exists():
            return {"recent_files": []}

        try:
            with open(self.recent_path, "r") as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    return {"recent_files": []}
                # Ensure 'recent_files' key exists
                if "recent_files" not in data or not isinstance(data.get("recent_files"), list):
                    data["recent_files"] = []
                # Normalize 'recent_remotes'
                rem = data.get("recent_remotes")
                if rem is None or not isinstance(rem, list):
                    data["recent_remotes"] = []
                return data
        except (json.JSONDecodeError, OSError):
            return {"recent_files": [], "recent_remotes": []}

    def save(self, files: List[str]) -> None:
        """
        Save recent files list to JSON file.

        Args:
            files: List of file paths to save.
        """
        # Ensure directory exists
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Preserve any existing remote entries
        existing = self._load_data()
        remotes = existing.get("recent_remotes", [])
        data = {"recent_files": files, "recent_remotes": remotes}
        try:
            # Write atomically: temp file + rename
            temp_path = self.recent_path.with_suffix(".tmp")
            with open(temp_path, "w") as f:
                json.dump(data, f, indent=2)
            temp_path.replace(self.recent_path)
        except OSError as e:
            print(f"Warning: Failed to save recent files: {e}")

    def load_remote(self) -> List[Dict]:
        """
        Load recent remote workspaces list.

        Returns:
            List of dicts with keys: url, workspace_id, label (optional).
        """
        data = self._load_data()
        remotes = data.get("recent_remotes", [])
        # Basic normalization to expected shape
        normalized = []
        for item in remotes:
            if isinstance(item, dict) and "url" in item:
                normalized.append({
                    "url": item.get("url"),
                    "workspace_id": item.get("workspace_id"),
                    "label": item.get("label")
                })
        return normalized

    def save_remote(self, remotes: List[Dict]) -> None:
        """
        Save recent remote workspaces list, preserving local recent files.
        """
        # Ensure directory exists
        self.data_dir.mkdir(parents=True, exist_ok=True)

        existing = self._load_data()
        files = existing.get("recent_files", [])
        data = {"recent_files": files, "recent_remotes": remotes}
        try:
            temp_path = self.recent_path.with_suffix(".tmp")
            with open(temp_path, "w") as f:
                json.dump(data, f, indent=2)
            temp_path.replace(self.recent_path)
        except OSError as e:
            print(f"Warning: Failed to save recent remote workspaces: {e}")

    def add_remote_entry(self, url: str, workspace_id: Optional[str] = None, label: Optional[str] = None) -> List[Dict]:
        """
        Add a remote workspace to recent list, deduping by URL/workspace_id and trimming to MAX_RECENT.

        Args:
            url: Full workspace URL (e.g., http://host:port/workspace/ws_abc123)
            workspace_id: Workspace ID (ws_xxxxxxxx)
            label: Optional display label (e.g., "hostname + ws_id")

        Returns:
            Updated list of recent remote entries.
        """
        remotes = self.load_remote()

        # Remove duplicates by URL or workspace_id
        def _is_same(entry: Dict) -> bool:
            if entry.get("url") == url:
                return True
            if workspace_id and entry.get("workspace_id") == workspace_id:
                return True
            return False

        remotes = [e for e in remotes if not _is_same(e)]

        # Insert new at front
        remotes.insert(0, {"url": url, "workspace_id": workspace_id, "label": label})

        # Trim
        remotes = remotes[: self.MAX_RECENT]

        # Persist
        self.save_remote(remotes)
        return remotes

    def get_remote_list(self) -> List[Dict]:
        """
        Get recent remote workspaces list without validation.
        """
        return self.load_remote()

    def remove_remote(self, url_or_workspace_id: str) -> List[Dict]:
        """
        Remove a remote entry by URL or workspace_id.
        """
        remotes = [e for e in self.load_remote() if e.get("url") != url_or_workspace_id and e.get("workspace_id") != url_or_workspace_id]
        self.save_remote(remotes)
        return remotes

    def move_remote_to_top(self, url_or_workspace_id: str) -> List[Dict]:
        """
        Move a remote entry to the top based on URL or workspace_id.
        """
        remotes = self.load_remote()
        target = None
        rest = []
        for e in remotes:
            if e.get("url") == url_or_workspace_id or e.get("workspace_id") == url_or_workspace_id:
                target = e
            else:
                rest.append(e)
        if target is None:
            return remotes
        new_list = [target] + rest
        self.save_remote(new_list)
        return new_list

    def add(self, file_path: str) -> List[str]:
        """
        Add file to recent list, removing duplicates and trimming to MAX_RECENT.

        Args:
            file_path: Absolute path to workflow file.

        Returns:
            Updated recent files list.
        """
        # Convert to absolute path
        abs_path = os.path.abspath(file_path)

        # Load current list
        recent = self.load()

        # Remove if already present
        recent = [p for p in recent if os.path.abspath(p) != abs_path]

        # Add to front
        recent.insert(0, abs_path)

        # Trim to max
        recent = recent[: self.MAX_RECENT]

        # Persist
        self.save(recent)

        return recent

    def get_list(self) -> List[str]:
        """
        Get recent files list, validating all paths exist.

        Removes non-existent files and persists cleaned list.

        Returns:
            List of existing recent file paths.
        """
        recent = self.load()

        # Filter to existing files
        existing = [p for p in recent if os.path.isfile(p)]

        # Persist cleaned list if changed
        if len(existing) != len(recent):
            self.save(existing)

        return existing

    def remove(self, file_path: str) -> List[str]:
        """
        Remove file from recent list.

        Args:
            file_path: Path to remove (will be normalized to absolute).

        Returns:
            Updated recent files list.
        """
        abs_path = os.path.abspath(file_path)
        recent = self.load()
        recent = [p for p in recent if os.path.abspath(p) != abs_path]
        self.save(recent)
        return recent

    def move_to_top(self, file_path: str) -> List[str]:
        """
        Move file to top of recent list (for recently accessed file).

        Args:
            file_path: Path to move to top.

        Returns:
            Updated recent files list.
        """
        return self.add(file_path)
