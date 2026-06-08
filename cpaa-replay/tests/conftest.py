"""Shared pytest fixtures for the CPAA replay unit suite.

Owns env wiring (SHADOW_DB / LIVE_DB into app config) and tempfile-backed
SQLite databases. NEVER uses :memory: (FC49: a fresh :memory: db per connect).
"""
import os
import sqlite3
import sys
import tempfile

import pytest

# --- locate the cpaa-replay project root and make `app` / `tools` importable ---
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

_SHADOW_SCHEMA = os.path.join(_ROOT, "schema", "shadow_schema.sql")
_LIVE_SCHEMA = os.path.join(_ROOT, "schema", "live_schema.sql")


def _make_db_file() -> str:
    """Create an empty tempfile path for a SQLite database (never :memory:)."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.unlink(path)  # remove the empty file so the schema load starts clean
    return path


def _load_schema(path: str, schema_file: str) -> None:
    """Apply a schema file to a fresh DB on a raw connection (executescript)."""
    with open(schema_file, "r", encoding="utf-8") as fh:
        schema_sql = fh.read()
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()


@pytest.fixture()
def db_paths(monkeypatch):
    """Create fresh tempfile shadow+live DBs and wire them into env + app config.

    Maps os.environ SHADOW_DB / LIVE_DB (FC49 / test-agent rule) plus the
    fail-closed secrets the app factory requires (SECRET_KEY, APP_PASSWORD).
    """
    shadow_path = _make_db_file()
    live_path = _make_db_file()
    _load_schema(shadow_path, _SHADOW_SCHEMA)
    _load_schema(live_path, _LIVE_SCHEMA)

    monkeypatch.setenv("SHADOW_DB", shadow_path)
    monkeypatch.setenv("LIVE_DB", live_path)
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("APP_PASSWORD", "test-password")

    yield {"shadow": shadow_path, "live": live_path}

    for p in (shadow_path, live_path):
        for suffix in ("", "-wal", "-shm"):
            try:
                os.unlink(p + suffix)
            except OSError:
                pass


@pytest.fixture()
def app(db_paths):
    """A configured Flask app bound to the tempfile DBs."""
    from app import create_app

    application = create_app()
    application.config.update(TESTING=True)
    return application


@pytest.fixture()
def client(app):
    """A test client for route-level checks."""
    return app.test_client()


@pytest.fixture()
def shadow_conn(app):
    """An open shadow connection in IMMEDIATE mode for direct model tests.

    Uses the app's own get_db opener so PRAGMA / row_factory match production
    exactly. Runs inside an app context in case get_db reads current_app.config.
    Yields an open transaction; the context manager owns commit/rollback.
    """
    from app.db import get_db

    with app.app_context():
        with get_db(immediate=True) as conn:
            yield conn


@pytest.fixture()
def live_ro_conn(app, db_paths):
    """A read-only connection to the tempfile live DB via the app opener."""
    from app.db import open_live_ro

    with app.app_context():
        conn = open_live_ro(db_paths["live"])
        try:
            yield conn
        finally:
            conn.close()
