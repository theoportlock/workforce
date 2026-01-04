"""
Recent files management for Workforce GUI.

Maintains a persistent list of recently opened workflow files using the
system user data directory via platformdirs, ensuring cross-platform compatibility.
"""

import json
import os
from pathlib import Path
from typing import List

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

    def save(self, files: List[str]) -> None:
        """
        Save recent files list to JSON file.

        Args:
            files: List of file paths to save.
        """
        # Ensure directory exists
        self.data_dir.mkdir(parents=True, exist_ok=True)

        data = {"recent_files": files}
        try:
            # Write atomically: temp file + rename
            temp_path = self.recent_path.with_suffix(".tmp")
            with open(temp_path, "w") as f:
                json.dump(data, f, indent=2)
            temp_path.replace(self.recent_path)
        except OSError as e:
            print(f"Warning: Failed to save recent files: {e}")

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
