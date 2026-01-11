"""
Wrapper presets management for Workforce GUI.

Per-machine persistent presets stored in the user's data directory via
platformdirs, using atomic writes to avoid corruption.

Structure:
{
  "presets": [
    {"name": "Bash", "wrapper": "bash -c \"{}\""},
    ...
  ]
}
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict

import platformdirs


DEFAULT_PRESETS: List[Dict[str, str]] = [
    {"name": "Bash", "wrapper": "bash -c \"{}\""},
    {"name": "Bash + env.sh", "wrapper": "bash -c '. env.sh && {}'"},
    {"name": "tmux", "wrapper": "tmux send-keys {} C-m"},
    {"name": "SSH", "wrapper": "ssh ADDRESS {}"},
    {"name": "GNU Parallel", "wrapper": "parallel {} ::: FILENAMES"},
    {"name": "Docker (TTY)", "wrapper": "docker run -it IMAGE {}"},
    {"name": "Export script", "wrapper": "echo {} >> commands.sh"},
    {"name": "Conda", "wrapper": "bash -lc \"conda activate ENV && {}\""},
    {"name": "nohup", "wrapper": "nohup {} &"},
]


class PresetManager:
    """Manages persistent wrapper presets per-machine."""

    FILE_NAME = "wrappers.json"

    def __init__(self) -> None:
        app_data_dir = platformdirs.user_data_dir(appname="workforce", appauthor="workforce")
        self.data_dir = Path(app_data_dir)
        self.path = self.data_dir / self.FILE_NAME

    def _atomic_save(self, data: Dict) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        tmp.replace(self.path)

    def _load_raw(self) -> Dict:
        if not self.path.exists():
            return {"presets": []}
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                obj = json.load(f)
                if isinstance(obj, dict) and "presets" in obj and isinstance(obj["presets"], list):
                    return obj
        except (OSError, json.JSONDecodeError):
            pass
        return {"presets": []}

    def ensure_defaults(self) -> None:
        obj = self._load_raw()
        if not obj.get("presets"):
            self._atomic_save({"presets": DEFAULT_PRESETS})

    def list(self) -> List[Dict[str, str]]:
        """Return list of presets; ensures defaults if empty."""
        self.ensure_defaults()
        return self._load_raw().get("presets", [])

    def save(self, presets: List[Dict[str, str]]) -> None:
        self._atomic_save({"presets": presets})

    def add(self, name: str, wrapper: str) -> List[Dict[str, str]]:
        presets = self.list()
        # remove any existing with same name
        presets = [p for p in presets if p.get("name") != name]
        presets.insert(0, {"name": name, "wrapper": wrapper})
        self.save(presets)
        return presets

    def update(self, name: str, wrapper: str) -> List[Dict[str, str]]:
        presets = self.list()
        updated = False
        for p in presets:
            if p.get("name") == name:
                p["wrapper"] = wrapper
                updated = True
                break
        if not updated:
            presets.insert(0, {"name": name, "wrapper": wrapper})
        self.save(presets)
        return presets

    def remove(self, name: str) -> List[Dict[str, str]]:
        presets = [p for p in self.list() if p.get("name") != name]
        self.save(presets)
        return presets
