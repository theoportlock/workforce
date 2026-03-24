"""Deprecated compatibility shim for recent file management.

This module has moved to ``workforce.recent`` and will be removed in a future
release.
"""

from warnings import warn

from workforce.recent import RecentFileManager

warn(
    "workforce.gui.recent is deprecated; import RecentFileManager from workforce.recent instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["RecentFileManager"]
