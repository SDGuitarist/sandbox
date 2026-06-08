"""Two-snapshot determinism comparison (core logic).

`validate_runs` reads two completed runs' persisted projection snapshots via
`read_snapshot`, asserts each run recorded `live_hash_pre == live_hash_post`
(the shadow-isolation proof, frozen #3), computes a field-level diff between the
two snapshots, and persists the verdict + diffs through `record_determinism`.

The comparison is the SINGLE place the snapshot field-diff is computed; the
write is delegated to `validation_models` (single writer of determinism_*).
This module never writes determinism_* directly and never commits — the route
owns the transaction (FC29).
"""

from __future__ import annotations

import json
import sqlite3

from app.constants import _PROJECTION_TABLES
from app.live_guard import live_content_hash
from app.snapshot_models import read_snapshot
from app.validation_models import record_determinism


def _diff_snapshots(
    snap_a: dict[str, dict[str, dict]],
    snap_b: dict[str, dict[str, dict]],
) -> list[dict]:
    """Field-level diff of two run snapshots.

    Walks _PROJECTION_TABLES in order; for each table compares the row dicts
    keyed by pk. A pk present in only one run, or a per-key value mismatch,
    yields one diff item {table_name, pk, key, value_a, value_b}. value_a/value_b
    are JSON-serialized scalar values (or None when the row/key is absent in that
    run). Ordering of the returned list is not relied upon — validation_models
    re-sorts by (table order, pk, key).
    """
    diffs: list[dict] = []
    for table in _PROJECTION_TABLES:
        rows_a = snap_a.get(table, {})
        rows_b = snap_b.get(table, {})
        for pk in sorted(set(rows_a) | set(rows_b)):
            row_a = rows_a.get(pk)
            row_b = rows_b.get(pk)
            keys = set()
            if row_a is not None:
                keys |= set(row_a)
            if row_b is not None:
                keys |= set(row_b)
            for key in sorted(keys):
                val_a = row_a.get(key) if row_a is not None else None
                val_b = row_b.get(key) if row_b is not None else None
                if val_a != val_b:
                    diffs.append(
                        {
                            "table_name": table,
                            "pk": pk,
                            "key": key,
                            "value_a": _encode(val_a),
                            "value_b": _encode(val_b),
                        }
                    )
    return diffs


def _encode(value: object | None) -> str | None:
    """Serialize a scalar snapshot value for storage in determinism_diffs."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def validate_runs(
    conn: sqlite3.Connection,
    run_a: str,
    run_b: str,
    live_ro: sqlite3.Connection,
) -> int:
    """Compare two completed runs and persist the determinism verdict.

    Reads both runs' snapshots, asserts each run recorded an unchanged live.db
    (`live_hash_pre == live_hash_post`) AND that the current live.db content hash
    still equals each run's recorded post-hash, computes the field-level diff,
    then records the verdict and diffs via record_determinism. Returns the new
    determinism_results id.

    Participates in the caller's BEGIN IMMEDIATE transaction; does NOT commit.
    `live_ro` is a read-only live.db connection supplied by the route.
    """
    current_live = live_content_hash(live_ro)
    _assert_live_unchanged(conn, run_a, current_live)
    _assert_live_unchanged(conn, run_b, current_live)

    snap_a = read_snapshot(conn, run_a)
    snap_b = read_snapshot(conn, run_b)

    diffs = _diff_snapshots(snap_a, snap_b)
    match = 0 if diffs else 1
    return record_determinism(conn, run_a, run_b, match, diffs)


def _assert_live_unchanged(
    conn: sqlite3.Connection, run_id: str, current_live: str
) -> None:
    """Assert a run's live.db hashes are equal and match the current live.db.

    Raises sqlite3.IntegrityError if the stored `live_hash_pre`/`live_hash_post`
    are missing, differ from each other, or differ from the current live.db
    content hash — any of which means shadow isolation (frozen #3) was violated.
    Fails CLOSED — the determinism verdict is never recorded for a run whose
    live.db was not provably unchanged.
    """
    row = conn.execute(
        "SELECT live_hash_pre, live_hash_post FROM replay_runs WHERE run_id = ?",
        (run_id,),
    ).fetchone()
    if row is None:
        raise sqlite3.IntegrityError(f"run not found: {run_id}")
    pre = row["live_hash_pre"]
    post = row["live_hash_post"]
    if pre is None or post is None or pre != post or post != current_live:
        raise sqlite3.IntegrityError(
            f"live.db not provably unchanged for run {run_id}"
        )
