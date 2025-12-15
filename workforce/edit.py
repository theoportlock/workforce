#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Compatibility shim: defer to the real workforce.edit package implementation.

This file keeps 'import workforce.edit' working while we migrated logic into
the workforce/edit package (graph.py, client.py, cli.py).
"""

import os
import importlib.machinery
import importlib.util

_pkg_init = os.path.join(os.path.dirname(__file__), "edit", "__init__.py")
if not os.path.exists(_pkg_init):
    raise ImportError(
        "workforce.edit package not found. Ensure 'workforce/edit/__init__.py' exists "
        "and remove this shim module (workforce/edit.py) to allow package import."
    )

_loader = importlib.machinery.SourceFileLoader("workforce._edit_pkg", _pkg_init)
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
_pkg_mod = importlib.util.module_from_spec(_spec)
_loader.exec_module(_pkg_mod)

# Re-export public names (graph helpers, cmd_* and main)
for _name, _val in list(_pkg_mod.__dict__.items()):
    if not _name.startswith("_"):
        globals()[_name] = _val

__all__ = [n for n in globals().keys() if not n.startswith("_")]
