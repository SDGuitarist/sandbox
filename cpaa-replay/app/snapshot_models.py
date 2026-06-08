"""Single writer/reader of the projection_snapshots table.

write_snapshot serializes every projection row (across _PROJECTION_TABLES) to a
deterministic JSON string keyed by (run_id, table_name, pk). read_snapshot reads
the stored projection back for field-level diffing by the validator. Neither
function commits — the caller owns the transaction (FC29).
"""

import json
import sqlite3

from app.constants import _PROJECTION_TABLES


def _pk_column(conn: sqlite3.Connection, table: str) -> str:
    """Return the single primary-key column name for a projection table."""
    for col in conn.execute(f"PRAGMA table_info({table})"):
        if col["pk"]:
            return col["name"]
    raise sqlite3.OperationalError(f"no primary key for table {table}")


def _row_to_dict(row: sqlite3.Row) -> dict:
    return {key: row[key] for key in row.keys()}


def _canonical_json(row_dict: dict) -> str:
    return json.dumps(
        row_dict,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def write_snapshot(conn: sqlite3.Connection, run_id: str) -> None:
    """Persist this run's projection: one row per projection row, JSON-serialized.

    Iterates _PROJECTION_TABLES in order; for each table selects every row
    ordered by its primary key (COLLATE BINARY) and inserts a snapshot row keyed
    by (run_id, table_name, pk) with a deterministic, stable-key-order JSON body.
    Participates in the caller's transaction; does NOT commit.
    """
    for table in _PROJECTION_TABLES:
        pk = _pk_column(conn, table)
        rows = conn.execute(
            f"SELECT * FROM {table} ORDER BY {pk} COLLATE BINARY ASC"
        ).fetchall()
        for row in rows:
            row_dict = _row_to_dict(row)
            conn.execute(
                "INSERT INTO projection_snapshots(run_id, table_name, pk, row_json) "
                "VALUES(?,?,?,?)",
                (run_id, table, str(row_dict[pk]), _canonical_json(row_dict)),
            )


def read_snapshot(conn: sqlite3.Connection, run_id: str) -> dict[str, dict[str, dict]]:
    """Return the stored projection for a run as {table_name: {pk: row_dict}}.

    Reads back the rows written by write_snapshot for field-level diffing by the
    validator. Read-only; does NOT commit.
    """
    result: dict[str, dict[str, dict]] = {table: {} for table in _PROJECTION_TABLES}
    rows = conn.execute(
        "SELECT table_name, pk, row_json FROM projection_snapshots WHERE run_id = ?",
        (run_id,),
    ).fetchall()
    for row in rows:
        result.setdefault(row["table_name"], {})[row["pk"]] = json.loads(row["row_json"])
    return result
