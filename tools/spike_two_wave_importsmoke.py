#!/usr/bin/env python3
"""Spike 0a integrated gate (pytest) — the pinned §3.4 gate, faithfully.

Two things happen against the assembled tree rooted at PKGSPIKE_ROOT:

1. IMPORT-SMOKE — `importlib`-import EVERY module under `pkgspike/`. This
   resolves cross-module imports at import time, so `pkgspike.routes` only
   passes if `pkgspike.database` is actually present in the integrated tree
   (the original cross-wave import-resolution premise). This is NOT static
   type checking — no type-checker is configured; it is import-time name
   resolution, a strict superset of `compileall` syntax compilation.

2. BOOT create_app() — construct the app via `pkgspike.factory.create_app()`,
   assert a teardown_appcontext handler is registered (H3 / FC3), then run an
   app-context cycle (H6 / FC39) so `init_db()` and the teardown actually fire.
   A bare import-smoke does NOT exercise this; booting create_app() is what
   catches the lifecycle seams that broke Run 083's integrated tree.

Run:  PKGSPIKE_ROOT=<assembled tree> .venv/bin/pytest tools/spike_two_wave_importsmoke.py
"""

import importlib
import os
import sys

import pytest

ROOT = os.environ.get("PKGSPIKE_ROOT")


def _ensure_path():
    if ROOT and ROOT not in sys.path:
        sys.path.insert(0, ROOT)


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
    _ensure_path()
    importlib.import_module(modname)


def test_root_set():
    assert ROOT, "PKGSPIKE_ROOT env var is required"
    assert _module_names(), "no pkgspike modules found in the assembled tree"


def test_boot_create_app():
    """Boot the app factory and exercise the app-context/teardown lifecycle.

    In the BROKEN assembled tree, create_app() calls init_db() bare and this
    raises `RuntimeError: Working outside of application context` — the gate
    FAILS, proving it catches the H6/H3 class, not just imports. In the
    assembly-FIXED tree it constructs cleanly and the context cycle succeeds.
    """
    _ensure_path()
    factory = importlib.import_module("pkgspike.factory")
    app = factory.create_app()  # raises in the broken tree (bare init_db)
    assert app.teardown_appcontext_funcs, \
        "teardown_appcontext handler not registered (H3 / FC3)"
    database = importlib.import_module("pkgspike.database")
    with app.app_context():
        assert database.query() == []  # exercises app-context DB access (H6)
    # context pop above fires the registered teardown_appcontext(close_db)
