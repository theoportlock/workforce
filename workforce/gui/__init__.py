from __future__ import annotations
#!/usr/bin/env python3
# Lightweight GUI package entrypoint. Exposes WorkflowApp and main().

import logging

from .state import GUIState
from .client import ServerClient


def main(
    base_url: str,
    wf_path: str = None,
    workspace_id: str = None,
    background: bool = True,
):
    """Lazy launcher to avoid importing Tk modules at package import time."""
    from .app import launch

    return launch(
        base_url, wf_path=wf_path, workspace_id=workspace_id, background=background
    )


def __getattr__(name: str):
    """Provide lazy access to Tk-heavy objects only when explicitly requested."""
    if name == "WorkflowApp":
        from .core import WorkflowApp

        return WorkflowApp
    raise AttributeError(name)


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)


# Keep __all__ explicit for clarity
__all__ = ["GUIState", "ServerClient", "main"]
