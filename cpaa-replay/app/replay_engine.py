"""Replay engine: run lifecycle orchestration, clean-room reset, dispatch, snapshot+hash.

Owns the 3-transaction replay sequence (pinned C):
  T1  lock-acquire (reap_stale_runs + start_run) -> commit so a concurrent
      409 path can read the RUNNING row from another connection.
  T2  one BEGIN IMMEDIATE: capture live_hash_pre -> reset_* (clean room) ->
      apply all events by event_id via DISPATCH -> write_snapshot ->
      canonical_hash -> capture live_hash_post -> mark_complete_pass.
  T3  any exception in T2 -> mark_aborted(run_id).

build_projection_at is a PURE function: it builds the point-in-time projection
into a private throwaway in-memory sqlite DB using the SAME apply_*/reset_*
handlers (the single apply implementation) and writes NOTHING to shadow/live.
"""

import sqlite3

from flask import current_app

from app.constants import DISPATCH, _PROJECTION_TABLES
from app.db import get_db, open_live_ro
from app.event_models import events_at_time, get_events
from app.live_guard import live_content_hash
from app.proj_auction import apply_auction, reset_auction
from app.proj_environmental import apply_environmental, reset_environmental
from app.proj_station import apply_station, reset_station
from app.proj_system import apply_system, reset_system
from app.run_models import (
    mark_aborted,
    mark_complete_pass,
    reap_stale_runs,
    start_run,
)
from app.serialization import canonical_hash
from app.snapshot_models import write_snapshot

# event_type -> apply handler (resolved from the DISPATCH handler-module name).
_APPLY = {
    "proj_station": apply_station,
    "proj_auction": apply_auction,
    "proj_environmental": apply_environmental,
    "proj_system": apply_system,
}
# clean-room reset, one per projection owner (one-writer-per-table preserved).
_RESETS = (reset_station, reset_auction, reset_environmental, reset_system)

# Projection schema for the throwaway in-memory DB used by build_projection_at.
# Mirrors the four projection tables from schema/shadow_schema.sql so the SAME
# apply_*/reset_* handlers run unchanged against it.
_PROJECTION_SCHEMA = """
CREATE TABLE station_state (
  station_id TEXT PRIMARY KEY, weight_kg REAL, temp_c REAL, status TEXT,
  last_heartbeat TEXT, sales_total_cents INTEGER NOT NULL DEFAULT 0);
CREATE TABLE auction_state (
  lot_id TEXT PRIMARY KEY, bid_high_cents INTEGER NOT NULL DEFAULT 0,
  bid_count INTEGER NOT NULL DEFAULT 0);
CREATE TABLE environmental_state (
  id INTEGER PRIMARY KEY CHECK (id = 1), temperature_c REAL, humidity_pct REAL,
  wind_speed_kmh REAL);
CREATE TABLE system_state (k TEXT PRIMARY KEY, v TEXT);
"""

# Primary key column per projection table (for reading rows into the result dict).
_PK = {
    "station_state": "station_id",
    "auction_state": "lot_id",
    "environmental_state": "id",
    "system_state": "k",
}


def _apply_all(conn, rows):
    """Dispatch each event row to its handler via DISPATCH. Returns count applied.

    Unknown event_type -> the handler set has none; record_anomaly for unmapped
    types is the ingest-time responsibility (events in the log are already mapped),
    so an unmapped type here is simply skipped without applying.
    """
    applied = 0
    for row in rows:
        handler_module = DISPATCH.get(row["event_type"])
        if handler_module is None:
            continue
        apply_fn = _APPLY.get(str(handler_module).rsplit(".", 1)[-1])
        if apply_fn is None:
            continue
        apply_fn(conn, row)
        applied += 1
    return applied


def run_replay():
    """Execute a full replay run as the 3-transaction sequence (pinned C).

    Returns (run_id, acquired):
      acquired True  -> COMPLETE_PASS committed; run_id is this run.
      acquired False -> a run is already RUNNING; run_id is the active run.
    """
    # --- T1: reap + guarded lock-acquire, then commit so the 409 path on a
    #     separate connection can read the RUNNING row. ---
    with get_db(immediate=True) as conn:
        reap_stale_runs(conn)
        run_id, acquired = start_run(conn)
        conn.commit()
    if not acquired:
        return run_id, False

    # --- T2: one BEGIN IMMEDIATE for reset + apply-all + snapshot + hash. ---
    live_db_path = current_app.config['LIVE_DB']
    try:
        with get_db(immediate=True) as conn:
            live_conn = open_live_ro(live_db_path)
            try:
                live_hash_pre = live_content_hash(live_conn)
            finally:
                live_conn.close()

            for reset_fn in _RESETS:
                reset_fn(conn)

            rows = get_events(conn)
            events_applied = _apply_all(conn, rows)

            write_snapshot(conn, run_id)
            projection_hash = canonical_hash(conn)

            live_conn = open_live_ro(live_db_path)
            try:
                live_hash_post = live_content_hash(live_conn)
            finally:
                live_conn.close()

            mark_complete_pass(
                conn,
                run_id,
                events_applied=events_applied,
                projection_hash=projection_hash,
                live_hash_pre=live_hash_pre,
                live_hash_post=live_hash_post,
            )
            conn.commit()
    except Exception:
        # --- T3: abort handler. The events log is append-only (never truncated). ---
        with get_db(immediate=True) as conn:
            mark_aborted(conn, run_id)
            conn.commit()
        raise

    return run_id, True


def build_projection_at(conn, t: str) -> dict[str, dict[str, dict]]:
    """Pure point-in-time projection: build into a throwaway in-memory sqlite using
    the SAME apply_*/reset_* handlers, then read into a dict. Writes NOTHING to
    shadow.db or live.db. (§8.1 exception b.)

    Returns {table_name: {pk: row_dict}}.
    """
    rows = events_at_time(conn, t)

    mem = sqlite3.connect(":memory:")
    mem.row_factory = sqlite3.Row
    try:
        mem.executescript(_PROJECTION_SCHEMA)
        with mem:
            for reset_fn in _RESETS:
                reset_fn(mem)
            _apply_all(mem, rows)

        result: dict[str, dict[str, dict]] = {}
        for table in _PROJECTION_TABLES:
            pk = _PK[table]
            table_rows = mem.execute(f"SELECT * FROM {table}").fetchall()
            result[table] = {str(r[pk]): dict(r) for r in table_rows}
        return result
    finally:
        mem.close()
