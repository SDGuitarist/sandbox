"""Gig model: schema, CRUD, venue-scoped queries, and dashboard analytics.

Models receive an open ``sqlite3.Connection`` with ``row_factory`` already set
to ``sqlite3.Row`` by ``get_db()``. This module NEVER opens connections or sets
``row_factory``. All writes use ``with conn:`` (no ``conn.commit()``, no bare
``BEGIN``). Timestamps use SQL ``datetime('now')`` only.
"""

import uuid
from sqlite3 import Row

GIG_SCHEMA = """
CREATE TABLE IF NOT EXISTS gigs (
  id TEXT PRIMARY KEY,
  venue_id TEXT NOT NULL REFERENCES venues(id) ON DELETE RESTRICT,
  date TEXT NOT NULL,  -- YYYY-MM-DD
  event_type TEXT CHECK(event_type IN ('wedding','corporate','restaurant','private_party','festival','public','other')),
  client_name TEXT,
  client_email TEXT,
  planned_set_summary TEXT,
  expected_pay_cents INTEGER CHECK(expected_pay_cents IS NULL OR expected_pay_cents >= 0),
  actual_pay_cents INTEGER CHECK(actual_pay_cents IS NULL OR actual_pay_cents >= 0),
  payment_status TEXT CHECK(payment_status IN ('unpaid','pending','paid')),
  status TEXT NOT NULL CHECK(status IN ('upcoming','played','cancelled')) DEFAULT 'upcoming',
  notes TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now')),
  CHECK(
    (actual_pay_cents IS NULL AND payment_status IS NULL)
    OR (actual_pay_cents IS NOT NULL AND payment_status IS NOT NULL)
  )
);
"""


def init_gig_schema(conn) -> None:
    conn.execute(GIG_SCHEMA)


def create_gig(conn, venue_id, date, event_type, client_name, client_email,
               planned_set_summary, expected_pay_cents, notes) -> str:
    gig_id = uuid.uuid4().hex[:8]
    with conn:
        conn.execute(
            """
            INSERT INTO gigs (
                id, venue_id, date, event_type, client_name, client_email,
                planned_set_summary, expected_pay_cents, actual_pay_cents,
                payment_status, status, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, 'upcoming', ?)
            """,
            (gig_id, venue_id, date, event_type, client_name, client_email,
             planned_set_summary, expected_pay_cents, notes),
        )
    return gig_id


def get_gig(conn, gig_id) -> Row | None:
    cur = conn.execute("SELECT * FROM gigs WHERE id = ?", (gig_id,))
    return cur.fetchone()


def list_gigs(conn, status=None) -> list[Row]:
    if status is None:
        cur = conn.execute(
            """
            SELECT g.*, v.name as venue_name
            FROM gigs g JOIN venues v ON g.venue_id = v.id
            ORDER BY g.date DESC
            """
        )
    else:
        cur = conn.execute(
            """
            SELECT g.*, v.name as venue_name
            FROM gigs g JOIN venues v ON g.venue_id = v.id
            WHERE g.status = ?
            ORDER BY g.date DESC
            """,
            (status,),
        )
    return cur.fetchall()


def update_gig(conn, gig_id, date, event_type, client_name, client_email,
               planned_set_summary, expected_pay_cents, actual_pay_cents,
               payment_status, notes) -> None:
    with conn:
        conn.execute(
            """
            UPDATE gigs SET
                date = ?,
                event_type = ?,
                client_name = ?,
                client_email = ?,
                planned_set_summary = ?,
                expected_pay_cents = ?,
                actual_pay_cents = ?,
                payment_status = ?,
                notes = ?,
                updated_at = datetime('now')
            WHERE id = ?
            """,
            (date, event_type, client_name, client_email, planned_set_summary,
             expected_pay_cents, actual_pay_cents, payment_status, notes, gig_id),
        )


def delete_gig(conn, gig_id) -> None:
    with conn:
        conn.execute("DELETE FROM gigs WHERE id = ?", (gig_id,))


def set_gig_status(conn, gig_id, new_status) -> None:
    with conn:
        conn.execute(
            "UPDATE gigs SET status = ?, updated_at = datetime('now') WHERE id = ?",
            (new_status, gig_id),
        )


def count_gigs_by_venue(conn, venue_id) -> int:
    cur = conn.execute(
        "SELECT COUNT(*) FROM gigs WHERE venue_id = ?", (venue_id,)
    )
    return cur.fetchone()[0]


def list_gigs_by_venue(conn, venue_id) -> list[Row]:
    cur = conn.execute(
        "SELECT * FROM gigs WHERE venue_id = ? ORDER BY date DESC", (venue_id,)
    )
    return cur.fetchall()


def count_played_gigs(conn) -> int:
    cur = conn.execute("SELECT COUNT(*) FROM gigs WHERE status = 'played'")
    return cur.fetchone()[0]


def total_revenue_cents(conn) -> int:
    cur = conn.execute(
        """
        SELECT COALESCE(SUM(g.actual_pay_cents), 0) + COALESCE(SUM(o.tips_cents), 0)
        FROM gigs g
        LEFT JOIN outcomes o ON o.gig_id = g.id
        WHERE g.status = 'played' AND g.payment_status = 'paid'
        """
    )
    return cur.fetchone()[0]


def top_venues(conn, limit=5) -> list[Row]:
    cur = conn.execute(
        """
        SELECT v.name, COUNT(g.id) as gig_count
        FROM venues v JOIN gigs g ON g.venue_id = v.id
        WHERE g.status = 'played'
        GROUP BY v.id ORDER BY gig_count DESC LIMIT ?
        """,
        (limit,),
    )
    return cur.fetchall()


def recent_gigs(conn, limit=10) -> list[Row]:
    cur = conn.execute(
        """
        SELECT g.*, v.name as venue_name
        FROM gigs g JOIN venues v ON g.venue_id = v.id
        ORDER BY g.date DESC LIMIT ?
        """,
        (limit,),
    )
    return cur.fetchall()


def monthly_revenue(conn, months=6) -> list[Row]:
    cur = conn.execute(
        """
        SELECT strftime('%Y-%m', g.date) as month,
               COALESCE(SUM(g.actual_pay_cents), 0) + COALESCE(SUM(o.tips_cents), 0) as total_cents
        FROM gigs g
        LEFT JOIN outcomes o ON o.gig_id = g.id
        WHERE g.status = 'played' AND g.payment_status = 'paid'
          AND g.date >= date('now', '-6 months')
        GROUP BY month ORDER BY month
        """
    )
    return cur.fetchall()
