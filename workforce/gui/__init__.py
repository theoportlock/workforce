from __future__ import annotations
#!/usr/bin/env python3
# Lightweight GUI package entrypoint. Exposes WorkflowApp and main().

import logging

# Use the renamed module: client.py (ServerClient is a client to the server)
from .state import GUIState
from .client import ServerClient
from .canvas import GraphCanvas
from .core import WorkflowApp  # WorkflowApp moved to core to avoid circular imports

# Lazy main launcher to avoid importing .app at module import time (prevents circular import)
def main(base_url: str, wf_path: str = None, workspace_id: str = None, background: bool = True):
    from .app import launch
    return launch(base_url, wf_path=wf_path, workspace_id=workspace_id, background=background)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)


# Keep __all__ explicit for clarity
__all__ = ["WorkflowApp", "GUIState", "ServerClient", "GraphCanvas", "main"]
