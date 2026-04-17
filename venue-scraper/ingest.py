"""Single-writer venue storage. Only this module writes to the venues table.

All SQL uses parameterized placeholders (?). No f-strings or .format() in SQL.
"""
from __future__ import annotations

import sqlite3
from typing import Literal

from models import VenueData


def insert_venue(conn: sqlite3.Connection, venue: VenueData) -> Literal["inserted", "skipped"]:
    """Insert a venue. Uses INSERT OR IGNORE for dedup on (source_url, source)."""
    cursor = conn.execute(
        "INSERT OR IGNORE INTO venues (name, source, source_url, data) VALUES (?, ?, ?, ?)",
        (venue.name, str(venue.source), venue.source_url, venue.model_dump_json()),
    )
    return "inserted" if cursor.rowcount > 0 else "skipped"
