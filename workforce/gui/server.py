"""
Compatibility shim: ServerClient was renamed to gui.client.ServerClient.
Existing imports that reference workforce.gui.server will continue to work.
"""
from .client import ServerClient

__all__ = ["ServerClient"]
