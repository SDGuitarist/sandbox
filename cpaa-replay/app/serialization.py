"""Canonical projection serialization + hash (RFC 8785-aligned, sole owner).

Hashes ONLY the four projection tables in `_PROJECTION_TABLES`, in that fixed
order. Never includes replay_runs, events, anomalies, projection_snapshots,
dedup_counters, determinism_*, or any `*_at` column. The byte recipe is frozen
in plan §8.8 and reproduced exactly here.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3

from app.constants import _PROJECTION_TABLES

# Primary-key column per projection table (plan §4.2 schema). Used only to build
# the per-table `ORDER BY <pk> COLLATE BINARY ASC` clause.
_PROJECTION_PK = {
    "station_state": "station_id",
    "auction_state": "lot_id",
    "environmental_state": "id",
    "system_state": "k",
}

_UNIT_SEP = b"\x1f"
_RECORD_SEP = b"\x1e"
_ROW_SEP = b"\x00"


def _serialize_row(row: sqlite3.Row) -> bytes:
    """Canonical JSON for one projection row.

    sort_keys orders columns; SQL NULL -> JSON null; REAL columns use Python's
    shortest-round-trip repr via json.dumps (no rounding); allow_nan=False
    forbids NaN/Infinity. ensure_ascii=False keeps UTF-8 text verbatim.
    """
    row_dict = {key: row[key] for key in row.keys()}
    text = json.dumps(
        row_dict,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return text.encode("utf-8")


def _table_block(conn: sqlite3.Connection, table: str) -> bytes:
    """One table's contribution: header + rows, per the §8.8 framed recipe.

    header = b"<table>\\x1f<rowcount>"; zero rows -> just header; else
    header + b"\\x00" + b"\\x00".join(row_jsons).
    """
    pk = _PROJECTION_PK[table]
    cur = conn.execute(f"SELECT * FROM {table} ORDER BY {pk} COLLATE BINARY ASC")
    rows = cur.fetchall()
    header = table.encode("utf-8") + _UNIT_SEP + str(len(rows)).encode("ascii")
    if not rows:
        return header
    return header + _ROW_SEP + _ROW_SEP.join(_serialize_row(r) for r in rows)


def canonical_hash(conn: sqlite3.Connection) -> str:
    """Return the 64-char lowercase hex SHA-256 of the canonical projection."""
    blocks = [_table_block(conn, table) for table in _PROJECTION_TABLES]
    payload = _RECORD_SEP.join(blocks)
    return hashlib.sha256(payload).hexdigest()
