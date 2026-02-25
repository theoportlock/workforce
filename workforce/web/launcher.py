"""Helpers for loading packaged frontend assets."""

from __future__ import annotations

from contextlib import contextmanager
from importlib import resources
from pathlib import Path
from typing import Iterator


@contextmanager
def frontend_assets() -> Iterator[Path]:
    """Yield a filesystem path to the packaged frontend static directory."""
    static_root = resources.files("workforce.web").joinpath("static")
    with resources.as_file(static_root) as path:
        yield path


def frontend_file(*relative_parts: str) -> str:
    """Return a filesystem path to a packaged frontend file."""
    with frontend_assets() as root:
        return str(root.joinpath(*relative_parts))
