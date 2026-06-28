"""Data-access layer for the Snippets app.

Each function receives an OPEN sqlite3 connection (`conn`) as its first
parameter; the caller (the routes layer) supplies it via the scaffold's
`get_db()`. Models never open their own connection.

The connection is expected to have `row_factory = sqlite3.Row`, so read
functions return rows that support `row['title']` access.

All SQL uses `?` placeholders -- user values are never string-formatted
into the query.
"""

import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS snippets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  body TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
)
"""


def init_db(conn: sqlite3.Connection) -> None:
    """Create the `snippets` table if it does not already exist.

    Single-statement DDL executed with `conn.execute` (not executescript).
    Commits internally.
    """
    conn.execute(SCHEMA)
    conn.commit()


def list_snippets(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Return all snippets, newest first. Read-only (no commit)."""
    cursor = conn.execute(
        "SELECT id, title, body, created_at, updated_at "
        "FROM snippets ORDER BY id DESC"
    )
    return cursor.fetchall()


def get_snippet(conn: sqlite3.Connection, snippet_id: int) -> sqlite3.Row | None:
    """Return one snippet by id, or None if not found. Read-only (no commit)."""
    cursor = conn.execute(
        "SELECT id, title, body, created_at, updated_at "
        "FROM snippets WHERE id = ?",
        (snippet_id,),
    )
    return cursor.fetchone()


def create_snippet(conn: sqlite3.Connection, title: str, body: str) -> int:
    """Insert one snippet and return the new row id. Commits internally."""
    cursor = conn.execute(
        "INSERT INTO snippets (title, body) VALUES (?, ?)",
        (title, body),
    )
    conn.commit()
    return cursor.lastrowid


def update_snippet(
    conn: sqlite3.Connection, snippet_id: int, title: str, body: str
) -> None:
    """Update a snippet's title/body and bump `updated_at`. Commits internally."""
    conn.execute(
        "UPDATE snippets "
        "SET title = ?, body = ?, updated_at = datetime('now') "
        "WHERE id = ?",
        (title, body, snippet_id),
    )
    conn.commit()


def delete_snippet(conn: sqlite3.Connection, snippet_id: int) -> None:
    """Delete a snippet by id. Commits internally."""
    conn.execute("DELETE FROM snippets WHERE id = ?", (snippet_id,))
    conn.commit()
