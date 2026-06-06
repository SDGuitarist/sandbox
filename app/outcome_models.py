"""Outcome model: outcomes table DDL, CRUD, and energy/tips analytics.

Models receive an open sqlite3.Connection (`conn`) with row_factory already set
to sqlite3.Row by the scaffold's get_db(). This module NEVER opens connections,
NEVER sets row_factory, and NEVER calls conn.commit(); all writes use `with conn:`.
"""

import uuid
from sqlite3 import Row

OUTCOME_SCHEMA = """
CREATE TABLE IF NOT EXISTS outcomes (
  id TEXT PRIMARY KEY,
  gig_id TEXT NOT NULL UNIQUE REFERENCES gigs(id) ON DELETE RESTRICT,
  audience_energy INTEGER NOT NULL CHECK(audience_energy BETWEEN 1 AND 5),
  audience_size_estimate INTEGER CHECK(audience_size_estimate IS NULL OR audience_size_estimate >= 0),
  song_highlights TEXT,
  song_struggles TEXT,
  audience_feedback TEXT,
  staff_feedback TEXT,
  personal_reflections TEXT,
  tips_cents INTEGER NOT NULL DEFAULT 0 CHECK(tips_cents >= 0),
  leads_generated INTEGER NOT NULL DEFAULT 0 CHECK(leads_generated >= 0),
  overall_rating INTEGER NOT NULL CHECK(overall_rating BETWEEN 1 AND 5),
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now'))
);
"""


def init_outcome_schema(conn) -> None:
    conn.execute(OUTCOME_SCHEMA)


def create_outcome(conn, gig_id, audience_energy, audience_size_estimate,
                   song_highlights, song_struggles, audience_feedback,
                   staff_feedback, personal_reflections, tips_cents,
                   leads_generated, overall_rating) -> str:
    new_id = uuid.uuid4().hex[:8]
    with conn:
        conn.execute(
            """
            INSERT INTO outcomes (
              id, gig_id, audience_energy, audience_size_estimate,
              song_highlights, song_struggles, audience_feedback,
              staff_feedback, personal_reflections, tips_cents,
              leads_generated, overall_rating
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (new_id, gig_id, audience_energy, audience_size_estimate,
             song_highlights, song_struggles, audience_feedback,
             staff_feedback, personal_reflections, tips_cents,
             leads_generated, overall_rating),
        )
    return new_id


def get_outcome_by_gig_id(conn, gig_id) -> Row | None:
    cur = conn.execute(
        "SELECT * FROM outcomes WHERE gig_id = ?",
        (gig_id,),
    )
    return cur.fetchone()


def update_outcome(conn, gig_id, audience_energy, audience_size_estimate,
                   song_highlights, song_struggles, audience_feedback,
                   staff_feedback, personal_reflections, tips_cents,
                   leads_generated, overall_rating) -> None:
    with conn:
        conn.execute(
            """
            UPDATE outcomes SET
              audience_energy = ?,
              audience_size_estimate = ?,
              song_highlights = ?,
              song_struggles = ?,
              audience_feedback = ?,
              staff_feedback = ?,
              personal_reflections = ?,
              tips_cents = ?,
              leads_generated = ?,
              overall_rating = ?,
              updated_at = datetime('now')
            WHERE gig_id = ?
            """,
            (audience_energy, audience_size_estimate, song_highlights,
             song_struggles, audience_feedback, staff_feedback,
             personal_reflections, tips_cents, leads_generated,
             overall_rating, gig_id),
        )


def avg_energy_by_venue(conn, venue_id) -> float | None:
    cur = conn.execute(
        """
        SELECT AVG(o.audience_energy)
        FROM outcomes o JOIN gigs g ON g.id = o.gig_id
        WHERE g.venue_id = ?
        """,
        (venue_id,),
    )
    row = cur.fetchone()
    return row[0] if row and row[0] is not None else None


def avg_audience_energy(conn) -> float | None:
    cur = conn.execute("SELECT AVG(audience_energy) FROM outcomes")
    row = cur.fetchone()
    return row[0] if row and row[0] is not None else None


def total_tips_cents(conn) -> int:
    cur = conn.execute("SELECT COALESCE(SUM(tips_cents), 0) FROM outcomes")
    return cur.fetchone()[0]
