"""Contacts model: schema, CRUD, and follow-up queries.

Models receive an open ``sqlite3.Connection`` with ``row_factory = sqlite3.Row``
already configured by the caller. This module NEVER opens a connection or sets
``row_factory``. Writes use ``with conn:`` for transaction management; there are
no bare ``conn.commit()`` calls and no explicit ``BEGIN``. ``IntegrityError``
(e.g. an FK violation) is allowed to propagate so routes can handle it.
"""

import uuid
from sqlite3 import Row

CONTACT_SCHEMA = """
CREATE TABLE IF NOT EXISTS contacts (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  role TEXT,
  organization TEXT,
  phone TEXT,
  email TEXT,
  met_at_gig_id TEXT REFERENCES gigs(id) ON DELETE SET NULL,
  venue_id TEXT REFERENCES venues(id) ON DELETE SET NULL,
  follow_up_needed INTEGER NOT NULL DEFAULT 0,  -- 0=false, 1=true
  follow_up_date TEXT,  -- YYYY-MM-DD, nullable
  follow_up_notes TEXT,
  notes TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now'))
);
"""


def init_contact_schema(conn) -> None:
    """Create the contacts table if it does not exist (idempotent)."""
    conn.execute(CONTACT_SCHEMA)


def create_contact(
    conn,
    name,
    role,
    organization,
    phone,
    email,
    met_at_gig_id,
    venue_id,
    follow_up_needed,
    follow_up_date,
    follow_up_notes,
    notes,
) -> str:
    """Insert a contact and return its generated 8-char id.

    May raise ``sqlite3.IntegrityError`` on an FK violation; the error is
    allowed to propagate to the calling route.
    """
    contact_id = uuid.uuid4().hex[:8]
    with conn:
        conn.execute(
            """
            INSERT INTO contacts (
              id, name, role, organization, phone, email,
              met_at_gig_id, venue_id, follow_up_needed,
              follow_up_date, follow_up_notes, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                contact_id,
                name,
                role,
                organization,
                phone,
                email,
                met_at_gig_id,
                venue_id,
                follow_up_needed,
                follow_up_date,
                follow_up_notes,
                notes,
            ),
        )
    return contact_id


def get_contact(conn, contact_id) -> Row | None:
    """Return the contact Row for ``contact_id``, or None if not found."""
    return conn.execute(
        "SELECT * FROM contacts WHERE id = ?",
        (contact_id,),
    ).fetchone()


def list_contacts(conn) -> list[Row]:
    """Return all contacts."""
    return conn.execute("SELECT * FROM contacts").fetchall()


def update_contact(
    conn,
    contact_id,
    name,
    role,
    organization,
    phone,
    email,
    met_at_gig_id,
    venue_id,
    follow_up_needed,
    follow_up_date,
    follow_up_notes,
    notes,
) -> None:
    """Update a contact and refresh ``updated_at``.

    May raise ``sqlite3.IntegrityError`` on an FK violation; the error is
    allowed to propagate to the calling route.
    """
    with conn:
        conn.execute(
            """
            UPDATE contacts SET
              name = ?,
              role = ?,
              organization = ?,
              phone = ?,
              email = ?,
              met_at_gig_id = ?,
              venue_id = ?,
              follow_up_needed = ?,
              follow_up_date = ?,
              follow_up_notes = ?,
              notes = ?,
              updated_at = datetime('now')
            WHERE id = ?
            """,
            (
                name,
                role,
                organization,
                phone,
                email,
                met_at_gig_id,
                venue_id,
                follow_up_needed,
                follow_up_date,
                follow_up_notes,
                notes,
                contact_id,
            ),
        )


def delete_contact(conn, contact_id) -> None:
    """Delete a contact. Always allowed."""
    with conn:
        conn.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))


def list_follow_ups(conn) -> list[Row]:
    """Return contacts needing follow-up, sorted by follow_up_date."""
    return conn.execute(
        "SELECT * FROM contacts WHERE follow_up_needed = 1 ORDER BY follow_up_date"
    ).fetchall()


def list_contacts_by_gig_id(conn, gig_id) -> list[Row]:
    """Return contacts met at the given gig."""
    return conn.execute(
        "SELECT * FROM contacts WHERE met_at_gig_id = ?",
        (gig_id,),
    ).fetchall()
