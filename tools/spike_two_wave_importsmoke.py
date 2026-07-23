#!/usr/bin/env python3
"""Spike 0a integrated import-smoke (pytest).

Imports EVERY module under `pkgspike/` in the assembled tree rooted at the path
given by the PKGSPIKE_ROOT env var. This is the pinned "integrated import gate"
of plan §0.0a step 2 — a strict superset of `compileall` (it resolves
cross-module imports at import time, so `pkgspike.routes` only passes if
`pkgspike.database` is actually present in the integrated tree).

Run:  PKGSPIKE_ROOT=<assembled tree> .venv/bin/pytest tools/spike_two_wave_importsmoke.py
"""

import importlib
import os
import sys

import pytest

ROOT = os.environ.get("PKGSPIKE_ROOT")


def _module_names():
    if not ROOT:
        return []
    pkg_dir = os.path.join(ROOT, "pkgspike")
    names = []
    for fn in sorted(os.listdir(pkg_dir)):
        if fn.endswith(".py"):
            stem = fn[:-3]
            names.append("pkgspike" if stem == "__init__" else f"pkgspike.{stem}")
    return names


@pytest.mark.parametrize("modname", _module_names())
def test_import_module(modname):
    assert ROOT, "PKGSPIKE_ROOT must be set to the assembled tree root"
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    importlib.import_module(modname)


def test_root_set():
    assert ROOT, "PKGSPIKE_ROOT env var is required"
    assert _module_names(), "no pkgspike modules found in the assembled tree"
