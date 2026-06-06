"""Venue model: schema DDL and CRUD for the `venues` table.

Models receive an open `sqlite3.Connection` (`conn`) whose `row_factory` is
already `sqlite3.Row`. This module never opens connections, never sets
`row_factory`, and never calls `conn.commit()` directly — all writes use the
`with conn:` context manager (which commits/rolls back atomically).
"""

import uuid
from sqlite3 import Row

VENUE_SCHEMA = """
CREATE TABLE IF NOT EXISTS venues (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  location TEXT,
  venue_type TEXT CHECK(venue_type IN ('hotel','restaurant','private','corporate','festival','other')),
  capacity_estimate INTEGER,
  vibe_notes TEXT,
  notes TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now')),
  UNIQUE(name COLLATE NOCASE)
);
"""


def init_venue_schema(conn) -> None:
    conn.execute(VENUE_SCHEMA)


def create_venue(conn, name, location, venue_type, capacity_estimate, vibe_notes, notes) -> str:
    venue_id = uuid.uuid4().hex[:8]
    with conn:
        conn.execute(
            """
            INSERT INTO venues
                (id, name, location, venue_type, capacity_estimate, vibe_notes, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (venue_id, name, location, venue_type, capacity_estimate, vibe_notes, notes),
        )
    return venue_id


def get_venue(conn, venue_id) -> Row | None:
    cur = conn.execute("SELECT * FROM venues WHERE id = ?", (venue_id,))
    return cur.fetchone()


def list_venues(conn) -> list[Row]:
    cur = conn.execute("SELECT * FROM venues ORDER BY name COLLATE NOCASE")
    return cur.fetchall()


def update_venue(conn, venue_id, name, location, venue_type, capacity_estimate, vibe_notes, notes) -> None:
    with conn:
        conn.execute(
            """
            UPDATE venues
               SET name = ?,
                   location = ?,
                   venue_type = ?,
                   capacity_estimate = ?,
                   vibe_notes = ?,
                   notes = ?,
                   updated_at = datetime('now')
             WHERE id = ?
            """,
            (name, location, venue_type, capacity_estimate, vibe_notes, notes, venue_id),
        )


def delete_venue(conn, venue_id) -> None:
    with conn:
        conn.execute("DELETE FROM venues WHERE id = ?", (venue_id,))


def venue_name_exists(conn, name, exclude_id=None) -> bool:
    if exclude_id is None:
        cur = conn.execute(
            "SELECT 1 FROM venues WHERE name = ? COLLATE NOCASE LIMIT 1",
            (name,),
        )
    else:
        cur = conn.execute(
            "SELECT 1 FROM venues WHERE name = ? COLLATE NOCASE AND id != ? LIMIT 1",
            (name, exclude_id),
        )
    return cur.fetchone() is not None
