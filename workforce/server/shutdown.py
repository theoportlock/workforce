"""
Shutdown utilities for Workforce server.

NOTE: Idle-based shutdown is no longer used with the new on-demand context lifecycle.
Contexts are created on first client connect and destroyed immediately on last client
disconnect (see routes.py client-disconnect endpoint). This module is kept for
backward compatibility but its functionality is superseded by explicit lifecycle
management in ServerContext.
"""

import logging

log = logging.getLogger(__name__)

