"""Debrief model: schema, CRUD, and keyword search.

Models receive an open ``conn`` (a ``sqlite3.Connection`` whose ``row_factory``
is already ``sqlite3.Row``). This module NEVER opens connections or sets
``row_factory``. All writes use ``with conn:`` (no ``conn.commit()``, no bare
``BEGIN``). Timestamps use SQL ``datetime('now')`` only.
"""

import uuid
from sqlite3 import Row

DEBRIEF_SCHEMA = """
CREATE TABLE IF NOT EXISTS debriefs (
  id TEXT PRIMARY KEY,
  gig_id TEXT NOT NULL UNIQUE REFERENCES gigs(id) ON DELETE RESTRICT,
  raw_text TEXT NOT NULL,
  key_takeaways TEXT,
  lessons_learned TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now'))
);
"""


def init_debrief_schema(conn) -> None:
    conn.execute(DEBRIEF_SCHEMA)


def create_debrief(conn, gig_id, raw_text, key_takeaways, lessons_learned) -> str:
    debrief_id = uuid.uuid4().hex[:8]
    with conn:
        conn.execute(
            "INSERT INTO debriefs (id, gig_id, raw_text, key_takeaways, lessons_learned) "
            "VALUES (?, ?, ?, ?, ?)",
            (debrief_id, gig_id, raw_text, key_takeaways, lessons_learned),
        )
    return debrief_id


def get_debrief_by_gig_id(conn, gig_id) -> Row | None:
    cur = conn.execute("SELECT * FROM debriefs WHERE gig_id = ?", (gig_id,))
    return cur.fetchone()


def update_debrief(conn, gig_id, raw_text, key_takeaways, lessons_learned) -> None:
    with conn:
        conn.execute(
            "UPDATE debriefs SET raw_text = ?, key_takeaways = ?, lessons_learned = ?, "
            "updated_at = datetime('now') WHERE gig_id = ?",
            (raw_text, key_takeaways, lessons_learned, gig_id),
        )


def search_debriefs(conn, query) -> list[Row]:
    cur = conn.execute(
        "SELECT d.*, g.date as gig_date, v.name as venue_name "
        "FROM debriefs d "
        "JOIN gigs g ON g.id = d.gig_id "
        "JOIN venues v ON v.id = g.venue_id "
        "WHERE d.raw_text LIKE '%' || ? || '%' "
        "   OR d.key_takeaways LIKE '%' || ? || '%' "
        "   OR d.lessons_learned LIKE '%' || ? || '%' "
        "ORDER BY g.date DESC",
        (query, query, query),
    )
    return cur.fetchall()
