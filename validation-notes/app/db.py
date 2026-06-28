"""SQLite connection helper for the Snippets app.

Per-connection settings (row_factory, PRAGMAs) are applied inside get_db()
so every caller gets a fully configured connection. The database is always a
real file on disk (never :memory:), with the path overridable via the
DATABASE environment variable so smoke tests can point at a temp file.
"""

import os
import sqlite3

# Default on-disk database path, relative to the project root. Overridable via
# the DATABASE environment variable.
_DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "snippets.db",
)


def get_db() -> sqlite3.Connection:
    """Open and return a configured SQLite connection.

    Returns a plain sqlite3.Connection (NOT a context manager) with
    row_factory set to sqlite3.Row so callers can access columns by name.
    """
    db_path = os.environ.get("DATABASE", _DEFAULT_DB_PATH)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
